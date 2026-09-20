from datetime import date, datetime
from io import StringIO
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import override_settings

from agents.agent import Agent
from agents.llm import LLMRefusal, LLMResult, LLMUsage
from agents.models import AgentConfig, PromptTemplate, UsageRecord
from agents.testing import FakeLLMClient
from agents.usage import used_today
from config.testing import ApiTestCase

JST = ZoneInfo("Asia/Tokyo")


class SeedTests(ApiTestCase):
    def test_seed_creates_agents_and_templates(self):
        self.assertEqual(AgentConfig.objects.count(), 4)
        self.assertEqual(PromptTemplate.objects.count(), 8)
        self.assertEqual(PromptTemplate.objects.get(label="多角的に検証して").prompt, "多角的に検証して")
        self.assertIn("htmlのコードブロック", PromptTemplate.objects.get(label="画面のイメージを出力して").prompt)
        self.assertFalse(AgentConfig.objects.get(key="hearing").callable_from_chat)

    def test_seed_does_not_overwrite(self):
        AgentConfig.objects.filter(key="hearing").update(role_prompt="調整済み")
        PromptTemplate.objects.exclude(label="アイデアを出して").delete()
        call_command("seed_agents", stdout=StringIO())
        self.assertEqual(AgentConfig.objects.get(key="hearing").role_prompt, "調整済み")
        self.assertEqual(PromptTemplate.objects.count(), 1)

    def test_templates_api_hides_inactive_and_role_prompts(self):
        PromptTemplate.objects.filter(label="多角的に検証して").update(is_active=False)
        response = self.client.get("/api/templates/")
        labels = [t["label"] for t in response.data["templates"]]
        self.assertEqual(len(labels), 7)
        self.assertEqual(labels[0], "見積もり（相場）")
        self.assertNotIn("role_prompt", str(response.data))


class AgentTests(ApiTestCase):
    def test_run_records_usage_with_role_prompt(self):
        FakeLLMClient.reset("こんにちは")
        FakeLLMClient.usage = LLMUsage(10, 20, 30, 40)
        result = Agent.load("hearing", self.user).run("やあ", purpose="chat")
        self.assertEqual(result.text, "こんにちは")
        call = FakeLLMClient.calls[0]
        self.assertEqual(call["system"], AgentConfig.objects.get(key="hearing").role_prompt)
        self.assertEqual(call["messages"], [{"role": "user", "content": "やあ"}])
        record = UsageRecord.objects.get()
        self.assertEqual(record.total_tokens, 100)
        self.assertEqual((record.agent_key, record.purpose), ("hearing", "chat"))

    def test_refusal_still_records_usage(self):
        error = LLMRefusal("拒否")
        error.result = LLMResult(usage=LLMUsage(5, 5), model="fake")
        FakeLLMClient.reset(error)
        with self.assertRaises(LLMRefusal):
            Agent.load("hearing", self.user).run("x", purpose="chat")
        self.assertEqual(used_today(self.user), 10)


class UsageLimitTests(ApiTestCase):
    def add_usage(self, tokens, day=None):
        UsageRecord.objects.create(
            user=self.user, date=day or datetime.now(JST).date(),
            agent_key="hearing", purpose="chat", input_tokens=tokens,
        )

    @override_settings(DAILY_TOKEN_LIMIT=1000)
    def test_limit_boundaries(self):
        self.add_usage(999)
        FakeLLMClient.reset("はい")
        self.assertEqual(self.client.post("/api/conversation/messages/", {"content": "a"}).status_code, 200)
        UsageRecord.objects.all().delete()
        self.add_usage(1000)
        response = self.client.post("/api/conversation/messages/", {"content": "a"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["code"], "daily_limit_reached")
        self.assertTrue(self.client.get("/api/me/").data["usage"]["limit_reached"])
        # 上限に達していても履歴は見られる
        self.assertEqual(self.client.get("/api/conversation/").status_code, 200)

    @override_settings(DAILY_TOKEN_LIMIT=1000)
    def test_usage_resets_at_midnight_jst(self):
        self.add_usage(1000, day=date(2026, 9, 17))
        # 日本時間 9/17 23:59 は上限のまま、9/18 0:00 で数え直しになる
        with mock.patch("django.utils.timezone.now", return_value=datetime(2026, 9, 17, 23, 59, tzinfo=JST)):
            self.assertEqual(used_today(self.user), 1000)
        with mock.patch("django.utils.timezone.now", return_value=datetime(2026, 9, 18, 0, 0, tzinfo=JST)):
            self.assertEqual(used_today(self.user), 0)

    def test_other_users_usage_is_not_counted(self):
        UsageRecord.objects.create(
            user=self.other, date=datetime.now(JST).date(), agent_key="hearing",
            purpose="chat", input_tokens=500,
        )
        self.assertEqual(used_today(self.user), 0)

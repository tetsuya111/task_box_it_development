"""1ユーザーあたり1日ごとの使用量（トークン数）の記録と上限の判定。"""

from django.conf import settings
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework import status

from config.exceptions import ApiError

from .models import UsageRecord


def record_usage(user, agent_key, purpose, result):
    usage = result.usage
    return UsageRecord.objects.create(
        user=user,
        # TIME_ZONE が Asia/Tokyo のため、日本時間の0:00で日付が切り替わる
        date=timezone.localdate(),
        agent_key=agent_key,
        purpose=purpose,
        model=result.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_creation_tokens=usage.cache_creation_tokens,
        cache_read_tokens=usage.cache_read_tokens,
    )


def used_today(user):
    total = UsageRecord.objects.filter(user=user, date=timezone.localdate()).aggregate(
        total=Sum(
            F("input_tokens") + F("output_tokens")
            + F("cache_creation_tokens") + F("cache_read_tokens")
        )
    )["total"]
    return total or 0


def usage_summary(user):
    used = used_today(user)
    limit = settings.DAILY_TOKEN_LIMIT
    return {"used": used, "limit": limit, "limit_reached": used >= limit}


def ensure_within_limit(user):
    """上限に達していれば 429 を返す。判定は処理の入口でのみ行う。"""
    if used_today(user) >= settings.DAILY_TOKEN_LIMIT:
        raise ApiError(
            "daily_limit_reached",
            "今日はたくさんお話ししたので、ここまでにさせてください。明日になるとまた使えます。",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

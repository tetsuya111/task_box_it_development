from io import StringIO
from unittest import mock

from django.core.management import call_command

from accounts import google
from accounts.models import User
from config.testing import ApiTestCase

CLAIMS = {"sub": "g-123", "email": "new@example.com", "email_verified": True, "name": "新規 花子"}


class GoogleLoginTests(ApiTestCase):
    def login(self, claims=CLAIMS, side_effect=None):
        with mock.patch.object(
            google, "verify_google_credential", return_value=claims, side_effect=side_effect
        ):
            return self.as_user(None).post("/api/auth/google/", {"credential": "token"})

    def test_creates_general_user_on_first_login(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(google_sub="g-123")
        self.assertEqual(user.role, User.Role.GENERAL)
        self.assertEqual(user.display_name, "新規 花子")
        self.assertFalse(user.has_usable_password())
        self.assertIn("access", response.data)
        cookie = response.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/api/auth/")

    def test_existing_user_is_reused(self):
        self.login()
        self.login()
        self.assertEqual(User.objects.filter(google_sub="g-123").count(), 1)

    def test_invalid_token_is_rejected(self):
        response = self.login(side_effect=google.InvalidGoogleToken("bad"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "invalid_google_token")

    def test_refresh_and_logout(self):
        client = self.as_user(None)
        with mock.patch.object(google, "verify_google_credential", return_value=CLAIMS):
            client.post("/api/auth/google/", {"credential": "token"})
        refreshed = client.post("/api/auth/refresh/")
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.data["user"]["email"], "new@example.com")
        client.post("/api/auth/logout/")
        client.cookies.pop("refresh_token", None)
        self.assertEqual(client.post("/api/auth/refresh/").status_code, 401)


class DevLoginTests(ApiTestCase):
    def test_dev_login_is_disabled_by_default(self):
        self.assertEqual(self.as_user(None).post("/api/auth/dev-login/").status_code, 404)

    def test_dev_login_when_enabled(self):
        with self.settings(ALLOW_DEV_LOGIN=True):
            response = self.as_user(None).post("/api/auth/dev-login/", {"admin": True}, format="json")
        self.assertEqual(response.data["user"]["role"], "admin")


class PermissionTests(ApiTestCase):
    def test_unauthenticated_is_rejected(self):
        for path in ("/api/me/", "/api/conversation/", "/api/templates/", "/api/admin/summaries/"):
            response = self.as_user(None).get(path)
            self.assertEqual(response.status_code, 401, path)
            self.assertEqual(response.data["code"], "not_authenticated")

    def test_general_user_cannot_use_admin_api(self):
        response = self.client.get("/api/admin/summaries/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.as_user(self.admin).get("/api/admin/summaries/").status_code, 200)

    def test_me_returns_role_and_usage(self):
        data = self.client.get("/api/me/").data
        self.assertEqual(data["user"]["role"], "general")
        self.assertEqual(data["usage"], {"used": 0, "limit": 300000, "limit_reached": False})

    def test_set_admin_command(self):
        call_command("set_admin", "irai@example.com", stdout=StringIO())
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.ADMIN)
        self.assertTrue(self.user.is_staff)

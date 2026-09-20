from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = "指定したメールアドレスのユーザーを管理者にする（--revoke で一般ユーザーに戻す）"

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--revoke", action="store_true")

    def handle(self, *args, email, revoke, **options):
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise CommandError(
                f"{email} のユーザーが見つかりません。先に一度Googleでログインしてください。"
            )
        user.role = User.Role.GENERAL if revoke else User.Role.ADMIN
        # Djangoの管理サイト（ロールプロンプト・テンプレの編集）にも入れるようにする
        user.is_staff = not revoke
        user.is_superuser = not revoke
        user.save(update_fields=["role", "is_staff", "is_superuser"])
        self.stdout.write(self.style.SUCCESS(f"{user.email}: role={user.role}"))

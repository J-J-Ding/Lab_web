from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import AuthAuditLog, User
from .helpers import AccountFixtures, PASSWORD


class RootCommandTests(AccountFixtures):
    def run_command(self, username, answers):
        output = StringIO()
        with patch('getpass.getpass', side_effect=answers):
            call_command('init_root', username=username, stdout=output)
        self.assertNotIn(PASSWORD, output.getvalue())

    def test_interactive_root_creation_is_hashed_and_audited(self):
        self.run_command('server-root', [PASSWORD, PASSWORD])
        user = User.objects.get(username='server-root')
        self.assertTrue(user.is_superuser and user.is_staff and user.is_active)
        self.assertEqual(user.role, 'CUSTOMER')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertTrue(AuthAuditLog.objects.filter(action='root.initialized', actor__isnull=True, target=user).exists())

    def test_existing_customer_is_not_promoted_or_password_reset(self):
        with self.assertRaises(CommandError):
            self.run_command('customer', [PASSWORD, PASSWORD])
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_superuser)
        self.assertTrue(self.customer.check_password(PASSWORD))

    def test_weak_mismatched_or_empty_password_creates_nothing(self):
        for answers in [('123', '123'), (PASSWORD, 'different'), ('', '')]:
            with self.subTest(answers=answers), self.assertRaises(CommandError):
                self.run_command('invalid-root', answers)
            self.assertFalse(User.objects.filter(username='invalid-root').exists())

    def test_command_does_not_accept_password_argument(self):
        with self.assertRaises((TypeError, CommandError)):
            call_command('init_root', username='forbidden', password=PASSWORD)

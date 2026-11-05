from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase


class UserTests(TestCase):
    def test_new_user_defaults_to_customer_without_privileges(self):
        user = get_user_model().objects.create_user(username="visitor", password="test-only-password")
        user.refresh_from_db()
        self.assertEqual(getattr(user, "role", None), "CUSTOMER")
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertNotEqual(user.password, "test-only-password")
        self.assertTrue(user.check_password("test-only-password"))

    def test_all_four_roles_persist_without_granting_staff(self):
        for role in ("ADMIN", "TEACHER", "STUDENT", "CUSTOMER"):
            with self.subTest(role=role):
                user = get_user_model().objects.create_user(username=role.lower())
                user.role = role
                user.save()
                user = get_user_model().objects.get(pk=user.pk)
                self.assertEqual(getattr(user, "role", None), role)
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)

    def test_database_rejects_unknown_role_and_root_role(self):
        user = get_user_model().objects.create_user(username="invalid-role")
        for value in ("ROOT", "UNKNOWN", ""):
            with self.subTest(value=value):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    get_user_model().objects.filter(pk=user.pk).update(role=value)

    def test_root_uses_superuser_flag_and_keeps_customer_role(self):
        user = get_user_model().objects.create_superuser(username="root", password="test-only-password")
        user.refresh_from_db()
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(getattr(user, "role", None), "CUSTOMER")

    def test_superuser_can_keep_teacher_role(self):
        user = get_user_model().objects.create_superuser(username="root-teacher", password="test-only-password")
        user.role = "TEACHER"
        user.save()
        user = get_user_model().objects.get(pk=user.pk)
        self.assertTrue(user.is_superuser)
        self.assertEqual(getattr(user, "role", None), "TEACHER")

    def test_superuser_rejects_disabled_privilege_flags(self):
        for flag in ("is_superuser", "is_staff"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                get_user_model().objects.create_superuser(username=flag, **{flag: False})

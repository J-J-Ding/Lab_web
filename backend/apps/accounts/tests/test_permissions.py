from django.contrib.auth import get_user_model

from .helpers import AccountFixtures, PASSWORD, NEW_PASSWORD, login_as, write


class PermissionTests(AccountFixtures):
    def test_customers_students_and_staff_cannot_access_management(self):
        for actor in (self.customer, self.student, self.staff):
            client = login_as(actor)
            for method, path in [('get', '/api/admin/users/'), ('post', '/api/admin/users/'), ('get', f'/api/admin/users/{self.teacher.pk}/'), ('patch', f'/api/admin/users/{self.teacher.pk}/'), ('post', f'/api/admin/users/{self.teacher.pk}/reset-password/')]:
                with self.subTest(actor=actor.username, method=method):
                    response = client.get(path) if method == 'get' else write(client, method, path)
                    self.assertEqual(response.status_code, 403)

    def test_admin_and_teacher_manage_ordinary_accounts(self):
        for actor in (self.admin, self.teacher):
            with self.subTest(actor=actor.username):
                client = login_as(actor)
                response = write(client, 'post', '/api/admin/users/', {'username': f'{actor.username}-created', 'password': PASSWORD, 'role': 'STUDENT'})
                self.assertEqual(response.status_code, 201)
                pk = response.json()['id']
                for role in ('CUSTOMER', 'TEACHER', 'STUDENT'):
                    response = write(client, 'patch', f'/api/admin/users/{pk}/', {'role': role, 'email': 'updated@example.org'})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()['role'], role)
                self.assertEqual(client.get(f'/api/admin/users/{pk}/').status_code, 200)
                self.assertEqual(write(client, 'post', f'/api/admin/users/{pk}/reset-password/', {'new_password': NEW_PASSWORD}).status_code, 204)
                self.assertTrue(get_user_model().objects.get(pk=pk).check_password(NEW_PASSWORD))
                self.assertEqual(write(client, 'patch', f'/api/admin/users/{pk}/', {'is_active': False}).status_code, 200)
                self.assertFalse(get_user_model().objects.get(pk=pk).is_active)

    def test_managers_cannot_create_admin_or_root_or_change_privileged_flags(self):
        for actor in (self.admin, self.teacher):
            client = login_as(actor)
            for extra in ({'role': 'ADMIN'}, {'role': 'ROOT'}, {'is_superuser': True}, {'is_staff': True}, {'groups': []}, {'user_permissions': []}):
                with self.subTest(actor=actor.username, extra=extra):
                    response = write(client, 'post', '/api/admin/users/', {'username': 'forbidden-created', 'password': PASSWORD, **extra})
                    self.assertIn(response.status_code, (400, 403))
                    self.assertFalse(get_user_model().objects.filter(username='forbidden-created').exists())
                    response = write(client, 'patch', f'/api/admin/users/{self.customer.pk}/', extra)
                    self.assertIn(response.status_code, (400, 403))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, 'CUSTOMER')
        self.assertFalse(self.customer.is_superuser)

    def test_managers_cannot_read_modify_or_reset_admin_or_any_root(self):
        for actor in (self.admin, self.teacher):
            client = login_as(actor)
            listing = client.get('/api/admin/users/').json()
            ids = [u['id'] for u in listing['results']]
            self.assertNotIn(self.admin.pk, ids)
            self.assertNotIn(self.root.pk, ids)
            for target in (self.admin, self.root):
                for method, suffix, payload in [('get', '', {}), ('patch', '', {'email': 'takeover@example.org'}), ('post', 'reset-password/', {'new_password': NEW_PASSWORD})]:
                    with self.subTest(actor=actor.username, target=target.username, method=method):
                        path = f'/api/admin/users/{target.pk}/{suffix}'
                        response = client.get(path) if method == 'get' else write(client, method, path, payload)
                        self.assertEqual(response.status_code, 404)
            for target in (self.admin, self.root):
                target.refresh_from_db()
                self.assertTrue(target.check_password(PASSWORD))
                self.assertEqual(target.email, '')

    def test_teacher_cannot_change_own_role_through_either_route(self):
        client = login_as(self.teacher)
        self.assertEqual(write(client, 'patch', '/api/auth/me/', {'role': 'ADMIN'}).status_code, 400)
        self.assertEqual(write(client, 'patch', f'/api/admin/users/{self.teacher.pk}/', {'role': 'STUDENT'}).status_code, 403)

    def test_root_manages_admin_but_api_cannot_create_another_root(self):
        client = login_as(self.root)
        self.assertEqual(client.get(f'/api/admin/users/{self.admin.pk}/').status_code, 200)
        response = write(client, 'post', '/api/admin/users/', {'username': 'new-admin', 'password': PASSWORD, 'role': 'ADMIN'})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()['is_superuser'])
        self.assertEqual(write(client, 'patch', f'/api/admin/users/{self.student.pk}/', {'role': 'ADMIN'}).status_code, 200)
        self.assertEqual(write(client, 'post', f'/api/admin/users/{self.admin.pk}/reset-password/', {'new_password': NEW_PASSWORD}).status_code, 204)
        for field in ('is_superuser', 'is_staff'):
            self.assertEqual(write(client, 'patch', f'/api/admin/users/{self.student.pk}/', {field: True}).status_code, 400)

    def test_reset_password_invalidates_all_target_sessions(self):
        target = login_as(self.student)
        manager = login_as(self.teacher)
        self.assertEqual(write(manager, 'post', f'/api/admin/users/{self.student.pk}/reset-password/', {'new_password': NEW_PASSWORD}).status_code, 204)
        self.assertEqual(target.get('/api/auth/me/').status_code, 403)
        self.assertEqual(login_as(self.student, NEW_PASSWORD).get('/api/auth/me/').status_code, 200)

    def test_disable_then_enable_does_not_revive_old_session(self):
        target = login_as(self.student)
        manager = login_as(self.teacher)
        path = f'/api/admin/users/{self.student.pk}/'
        self.assertEqual(write(manager, 'patch', path, {'is_active': False}).status_code, 200)
        # Re-enable before the old session makes any request.
        self.assertEqual(write(manager, 'patch', path, {'is_active': True}).status_code, 200)
        self.assertEqual(target.get('/api/auth/me/').status_code, 403)
        self.assertEqual(login_as(self.student).get('/api/auth/me/').status_code, 200)

    def test_disabled_user_cannot_use_session_or_login(self):
        target = login_as(self.student)
        manager = login_as(self.teacher)
        self.assertEqual(write(manager, 'patch', f'/api/admin/users/{self.student.pk}/', {'is_active': False}).status_code, 200)
        self.assertEqual(target.get('/api/auth/me/').status_code, 403)
        response = write(manager, 'post', '/api/auth/login/', {'username': 'student', 'password': PASSWORD})
        self.assertEqual(response.status_code, 400)

    def test_demotion_changes_existing_session_permissions(self):
        teacher = login_as(self.teacher)
        root = login_as(self.root)
        self.assertEqual(write(root, 'patch', f'/api/admin/users/{self.teacher.pk}/', {'role': 'STUDENT'}).status_code, 200)
        self.assertEqual(teacher.get('/api/admin/users/').status_code, 403)

    def test_pagination_is_bounded_and_missing_target_returns_404(self):
        client = login_as(self.root)
        response = client.get('/api/admin/users/?page_size=2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 2)
        self.assertIsNotNone(response.json()['next'])
        self.assertEqual(client.get('/api/admin/users/999999/').status_code, 404)
        self.assertEqual(write(client, 'patch', f'/api/admin/users/{self.customer.pk}/', {'email': 'invalid'}).status_code, 400)

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


class AuthenticationAndSessionTests(TestCase):

    def setUp(self):
        self.client = Client(SERVER_NAME="127.0.0.1")
        self.customer_user = User.objects.create_user(
            username="Test Customer",
            email="customer@example.com",
            password="CustomerPass123!"
        )
        self.admin_user = User.objects.create_superuser(
            username="testadmin",
            email="admin@example.com",
            password="AdminPass123!"
        )
        self.inactive_user = User.objects.create_user(
            username="Inactive User",
            email="inactive@example.com",
            password="InactivePass123!",
            is_active=False
        )

    # TEST 1: Customer logs in -> Customer Dashboard opens
    def test_customer_login_dashboard_opens(self):
        response = self.client.post(
            reverse("login"),
            {"username": "Test Customer", "password": "CustomerPass123!"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertEqual(response.context["user"].username, "Test Customer")
        self.assertContains(response, "Test Customer")
        self.assertContains(response, "My Profile")

    # TEST 2: Customer logs out -> Session is cleared
    def test_customer_logout_session_cleared(self):
        self.client.login(username="Test Customer", password="CustomerPass123!")
        # Test POST logout
        response = self.client.post(reverse("logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)

        # Test GET logout
        self.client.login(username="Test Customer", password="CustomerPass123!")
        response = self.client.get(reverse("logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)

    # TEST 3: Admin logs in -> Django Administration opens
    def test_admin_login_and_admin_opens(self):
        response = self.client.post(
            "/admin/login/",
            {"username": "testadmin", "password": "AdminPass123!"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertTrue(response.context["user"].is_staff)
        self.assertContains(response, "Site administration")

    # TEST 4: Admin logs out -> Session is cleared
    def test_admin_logout_session_cleared(self):
        self.client.login(username="testadmin", password="AdminPass123!")
        response = self.client.get("/admin/logout/", follow=True)
        self.assertEqual(response.status_code, 200)
        # Verify access to admin is now denied
        admin_response = self.client.get("/admin/")
        self.assertEqual(admin_response.status_code, 302)
        self.assertIn("/admin/login/", admin_response.url)

    # TEST 5: Normal customer attempts to open /admin/ -> Access is denied
    def test_normal_customer_denied_admin_access(self):
        self.client.login(username="Test Customer", password="CustomerPass123!")
        response = self.client.get("/admin/", follow=True)
        self.assertEqual(response.status_code, 200)
        # Should be redirected to admin login with error message and logout link
        self.assertContains(response, "You are authenticated as Test Customer, but are not authorized to access this page")
        self.assertContains(response, "Log out of Test Customer")
        self.assertNotContains(response, "Site administration")

    # TEST 6: Admin attempts to open customer dashboard -> Correct behavior is maintained
    def test_admin_opens_customer_dashboard(self):
        self.client.login(username="testadmin", password="AdminPass123!")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, testadmin! 👋")

    # TEST 7: Customer in normal window, Admin in Incognito window -> Both work independently
    def test_simultaneous_independent_sessions(self):
        normal_client = Client(SERVER_NAME="127.0.0.1")
        incognito_client = Client(SERVER_NAME="127.0.0.1")

        # Customer logs into normal client
        normal_client.post(
            reverse("login"),
            {"username": "Test Customer", "password": "CustomerPass123!"}
        )
        # Admin logs into incognito client
        incognito_client.post(
            "/admin/login/",
            {"username": "testadmin", "password": "AdminPass123!"}
        )

        # Normal client dashboard
        resp1 = normal_client.get(reverse("dashboard"))
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.context["user"].username, "Test Customer")

        # Incognito client admin
        resp2 = incognito_client.get("/admin/")
        self.assertEqual(resp2.status_code, 200)
        self.assertContains(resp2, "Site administration")

        # Normal client still denied admin
        resp3 = normal_client.get("/admin/", follow=True)
        self.assertContains(resp3, "You are authenticated as Test Customer, but are not authorized to access this page")

    # TEST 8: Switch from Customer to Admin in the same browser -> Correct logout and account switching
    def test_switch_customer_to_admin_same_browser(self):
        # 1. Customer logs in
        self.client.post(
            reverse("login"),
            {"username": "Test Customer", "password": "CustomerPass123!"}
        )
        dashboard_resp = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard_resp, "Test Customer")

        # 2. Customer logs out (via the admin error note link)
        logout_resp = self.client.get(reverse("logout") + "?next=/admin/login/", follow=True)
        self.assertEqual(logout_resp.status_code, 200)
        self.assertNotContains(logout_resp, "You are authenticated as")

        # 3. Admin logs in
        admin_resp = self.client.post(
            "/admin/login/",
            {"username": "testadmin", "password": "AdminPass123!"},
            follow=True
        )
        self.assertEqual(admin_resp.status_code, 200)
        self.assertContains(admin_resp, "Site administration")

    # TEST 9: Invalid password -> Login is rejected
    def test_invalid_password_rejected(self):
        response = self.client.post(
            reverse("login"),
            {"username": "Test Customer", "password": "WrongPassword999!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password. Please try again.")

    # TEST 10: Refresh the page after login -> Correct user identity remains displayed
    def test_refresh_preserves_identity(self):
        self.client.login(username="Test Customer", password="CustomerPass123!")
        # First visit
        resp1 = self.client.get(reverse("dashboard"))
        self.assertContains(resp1, "Welcome, Test Customer! 👋")
        # Refresh (second request)
        resp2 = self.client.get(reverse("dashboard"))
        self.assertContains(resp2, "Welcome, Test Customer! 👋")

    # Additional security & edge-case tests
    def test_inactive_user_cannot_login(self):
        response = self.client.post(
            reverse("login"),
            {"username": "Inactive User", "password": "InactivePass123!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid username or password. Please try again.")

    def test_unauthenticated_dashboard_redirects(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/?next=/accounts/dashboard/", response.url)

    def test_customer_registration_success(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "New Customer",
                "password1": "SecurePass1234!",
                "password2": "SecurePass1234!",
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="New Customer").exists())

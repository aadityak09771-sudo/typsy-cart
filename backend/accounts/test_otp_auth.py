import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailOTP
from delivery.models import DeliveryPartner

User = get_user_model()


class EmailOTPAuthenticationTests(TestCase):

    def setUp(self):
        self.client = Client(SERVER_NAME="127.0.0.1")

        # 1. Active Customer
        self.customer = User.objects.create_user(
            username="Anya Sharma",
            email="anya@tipsycart.in",
            password="AnyaCustomerPass123!"
        )

        # 2. Active Delivery Partner
        self.driver_user = User.objects.create_user(
            username="priya_driver",
            email="priya@tipsycart.in",
            password="PriyaDriverPass123!"
        )
        self.delivery_partner = DeliveryPartner.objects.create(
            user=self.driver_user,
            full_name="Priya Singh",
            phone="9876501234",
            email="priya@tipsycart.in",
            vehicle_type="scooter",
            is_active=True
        )

        # 3. Inactive Delivery Partner
        self.inactive_driver_user = User.objects.create_user(
            username="inactive_driver",
            email="inactive_driver@tipsycart.in",
            password="InactiveDriverPass123!"
        )
        self.inactive_delivery_partner = DeliveryPartner.objects.create(
            user=self.inactive_driver_user,
            full_name="Inactive Driver",
            phone="9876509999",
            email="inactive_driver@tipsycart.in",
            vehicle_type="scooter",
            is_active=False
        )

        # 4. Superuser Admin (auto-created by post_migrate)
        self.admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "email": "admin@tipsycart.in",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            }
        )
        self.admin_user.set_password("AKASH1234")
        self.admin_user.save()

    # -------------------------------------------------------------
    # 1. Customer requests OTP & 2. Resend successfully sends email
    # -------------------------------------------------------------
    @patch("accounts.services.otp_service.send_otp_email")
    def test_01_customer_requests_otp_and_resend_sends_email(self, mock_send):
        mock_send.return_value = (True, "mock-resend-msg-id-1234")

        response = self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("6-digit verification code has been sent", data["message"])
        self.assertTrue(mock_send.called)

        # Check that OTP record was stored in DB
        otp_record = EmailOTP.objects.filter(email="anya@tipsycart.in", purpose="customer_login", is_used=False).first()
        self.assertIsNotNone(otp_record)
        # Ensure raw OTP is not stored plain-text in DB
        self.assertTrue(otp_record.otp_hash.startswith("pbkdf2_sha256$"))

    # -------------------------------------------------------------
    # 3. Customer enters correct OTP & 4. Logged in and redirected to dashboard
    # -------------------------------------------------------------
    @patch("accounts.services.otp_service.send_otp_email")
    def test_03_04_customer_enters_correct_otp_and_redirects(self, mock_send):
        mock_send.return_value = (True, "msg-id-123")

        # 1. Request OTP
        self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "purpose": "customer_login"}),
            content_type="application/json"
        )
        otp_record = EmailOTP.objects.filter(email="anya@tipsycart.in", is_used=False).first()
        otp_record.set_otp("123456")
        otp_record.save()

        # 2. Verify OTP
        response = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "otp": "123456", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["redirect_url"], "/dashboard/")

        # 3. Check customer session is active
        dashboard_res = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_res.status_code, 200)
        self.assertEqual(dashboard_res.context["user"], self.customer)

    # -------------------------------------------------------------
    # 5. Incorrect OTP is rejected
    # -------------------------------------------------------------
    @patch("accounts.services.otp_service.send_otp_email")
    def test_05_incorrect_otp_rejected(self, mock_send):
        mock_send.return_value = (True, "msg-id-123")

        self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "purpose": "customer_login"}),
            content_type="application/json"
        )
        otp_record = EmailOTP.objects.filter(email="anya@tipsycart.in", is_used=False).first()
        otp_record.set_otp("888999")
        otp_record.save()

        # Submit wrong OTP
        response = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "otp": "000000", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("Invalid verification code", data["error"])

        # Check attempts counter incremented
        otp_record.refresh_from_db()
        self.assertEqual(otp_record.attempts, 1)

    # -------------------------------------------------------------
    # 6. Expired OTP is rejected
    # -------------------------------------------------------------
    def test_06_expired_otp_rejected(self):
        otp_record = EmailOTP.objects.create(
            email="anya@tipsycart.in",
            purpose="customer_login",
            expires_at=timezone.now() - timedelta(minutes=1),
            is_used=False
        )
        otp_record.set_otp("654321")
        otp_record.save()

        response = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "otp": "654321", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("expired", data["error"].lower())

    # -------------------------------------------------------------
    # 7. Reused OTP is rejected
    # -------------------------------------------------------------
    def test_07_reused_otp_rejected(self):
        otp_record = EmailOTP.objects.create(
            email="anya@tipsycart.in",
            purpose="customer_login",
            expires_at=timezone.now() + timedelta(minutes=5),
            is_used=True  # Already used
        )
        otp_record.set_otp("112233")
        otp_record.save()

        response = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "otp": "112233", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("No active verification code found", data["error"])

    # -------------------------------------------------------------
    # 8. Resend cooldown and attempt limits work
    # -------------------------------------------------------------
    @patch("accounts.services.otp_service.send_otp_email")
    def test_08_resend_cooldown_and_max_attempts(self, mock_send):
        mock_send.return_value = (True, "msg-id-123")

        # 8a. Send first OTP
        res1 = self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(res1.status_code, 200)

        # 8b. Attempt immediate second send -> Should trigger cooldown rejection
        res2 = self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(res2.status_code, 400)
        data2 = res2.json()
        self.assertFalse(data2["success"])
        self.assertIn("Please wait", data2["error"])

        # 8c. Test 5 failed attempts locks OTP
        otp_record = EmailOTP.objects.filter(email="anya@tipsycart.in", is_used=False).first()
        otp_record.set_otp("999999")
        otp_record.save()

        for i in range(1, 5):
            res = self.client.post(
                reverse("verify_otp"),
                data=json.dumps({"email": "anya@tipsycart.in", "otp": "000000", "purpose": "customer_login"}),
                content_type="application/json"
            )
            self.assertEqual(res.status_code, 400)

        # 5th failed attempt -> locks the OTP
        res5 = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "otp": "000000", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(res5.status_code, 400)
        self.assertIn("Maximum attempts reached", res5.json()["error"])

        otp_record.refresh_from_db()
        self.assertTrue(otp_record.is_used)

    # -------------------------------------------------------------
    # 9. Customer cannot access Delivery Partner or Admin pages
    # -------------------------------------------------------------
    def test_09_customer_cannot_access_delivery_or_admin_pages(self):
        self.client.force_login(self.customer)

        # Try to access Delivery Dashboard
        driver_res = self.client.get(reverse("delivery:dashboard"))
        # Should be redirected to delivery login
        self.assertEqual(driver_res.status_code, 302)
        self.assertIn("/delivery/login/", driver_res.url)

        # Try to access Admin Portal
        admin_res = self.client.get("/admin/", follow=True)
        # Should not show Site administration
        self.assertNotContains(admin_res, "Site administration")
        self.assertContains(admin_res, "not authorized to access this page")

    # -------------------------------------------------------------
    # 10. Delivery Partner can log in and access only their own authorized dashboard
    # -------------------------------------------------------------
    @patch("accounts.services.otp_service.send_otp_email")
    def test_10_delivery_partner_login_and_dashboard(self, mock_send):
        mock_send.return_value = (True, "msg-id-123")

        # 1. Driver requests OTP
        send_res = self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "priya@tipsycart.in", "purpose": "delivery_login"}),
            content_type="application/json"
        )
        self.assertEqual(send_res.status_code, 200)

        otp_record = EmailOTP.objects.filter(email="priya@tipsycart.in", is_used=False).first()
        otp_record.set_otp("445566")
        otp_record.save()

        # 2. Driver verifies OTP
        verify_res = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "priya@tipsycart.in", "otp": "445566", "purpose": "delivery_login"}),
            content_type="application/json"
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.json()["redirect_url"], "/delivery/dashboard/")

        # 3. Driver opens dashboard
        dash_res = self.client.get(reverse("delivery:dashboard"))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "Priya Singh")

    # -------------------------------------------------------------
    # 11. Inactive or unauthorized delivery partner cannot log in
    # -------------------------------------------------------------
    @patch("accounts.services.otp_service.send_otp_email")
    def test_11_inactive_or_unauthorized_driver_rejected(self, mock_send):
        # 11a. Inactive driver requests OTP
        res1 = self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "inactive_driver@tipsycart.in", "purpose": "delivery_login"}),
            content_type="application/json"
        )
        self.assertEqual(res1.status_code, 400)
        self.assertIn("deactivated", res1.json()["error"].lower())

        # 11b. Non-driver customer attempts delivery_login
        res2 = self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "purpose": "delivery_login"}),
            content_type="application/json"
        )
        self.assertEqual(res2.status_code, 400)
        self.assertIn("No active Delivery Partner account found", res2.json()["error"])

    # -------------------------------------------------------------
    # 12. Forgot Password OTP works and allows a secure password update
    # 13. Old password no longer works after password reset
    # -------------------------------------------------------------
    @patch("accounts.services.otp_service.send_otp_email")
    def test_12_13_forgot_password_flow_and_old_password_invalidation(self, mock_send):
        mock_send.return_value = (True, "msg-id-123")

        # Step 1: Send forgot password OTP
        send_res = self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "purpose": "forgot_password"}),
            content_type="application/json"
        )
        self.assertEqual(send_res.status_code, 200)

        otp_record = EmailOTP.objects.filter(email="anya@tipsycart.in", purpose="forgot_password", is_used=False).first()
        otp_record.set_otp("778899")
        otp_record.save()

        # Step 2: Verify reset OTP -> returns signed reset token
        verify_res = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": "anya@tipsycart.in", "otp": "778899", "purpose": "forgot_password"}),
            content_type="application/json"
        )
        self.assertEqual(verify_res.status_code, 200)
        reset_token = verify_res.json()["reset_token"]
        self.assertTrue(len(reset_token) > 20)

        # Step 3: Apply new password
        reset_res = self.client.post(
            reverse("reset_password"),
            data=json.dumps({
                "reset_token": reset_token,
                "new_password": "BrandNewPassword2026!",
                "confirm_password": "BrandNewPassword2026!"
            }),
            content_type="application/json"
        )
        self.assertEqual(reset_res.status_code, 200)
        self.assertTrue(reset_res.json()["success"])

        # Step 4: Verify old password fails
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.check_password("AnyaCustomerPass123!"))

        # Step 5: Verify new password succeeds
        self.assertTrue(self.customer.check_password("BrandNewPassword2026!"))

    # -------------------------------------------------------------
    # 14. Admin login remains unchanged and fully functional
    # -------------------------------------------------------------
    def test_14_admin_login_unchanged_and_functional(self):
        admin_login_res = self.client.post(
            "/admin/login/",
            {"username": "admin", "password": "AKASH1234"},
            follow=True
        )
        self.assertEqual(admin_login_res.status_code, 200)
        self.assertTrue(admin_login_res.context["user"].is_authenticated)
        self.assertTrue(admin_login_res.context["user"].is_staff)
        self.assertContains(admin_login_res, "Site administration")

    # -------------------------------------------------------------
    # 15. Logout and session behavior work correctly
    # -------------------------------------------------------------
    def test_15_logout_and_session_cleared(self):
        self.client.force_login(self.customer)
        self.assertTrue(self.client.get(reverse("dashboard")).context["user"].is_authenticated)

        # Customer logs out
        logout_res = self.client.post(reverse("logout"), follow=True)
        self.assertEqual(logout_res.status_code, 200)
        self.assertFalse(logout_res.context["user"].is_authenticated)

    # -------------------------------------------------------------
    # 16. New customer passwordless sign-up via OTP (no name or password asked)
    # -------------------------------------------------------------
    @patch("accounts.services.otp_service.send_otp_email")
    def test_16_new_customer_passwordless_signup_via_otp(self, mock_send):
        mock_send.return_value = (True, "new-user-msg-id-123")
        new_email = "pooja.verma@example.com"

        # Verify user does not exist initially
        self.assertFalse(User.objects.filter(email__iexact=new_email).exists())

        # 1. Request OTP for brand new email
        send_res = self.client.post(
            reverse("send_otp"),
            data=json.dumps({"email": new_email, "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(send_res.status_code, 200)
        self.assertTrue(send_res.json()["success"])

        otp_record = EmailOTP.objects.filter(email=new_email, is_used=False).first()
        otp_record.set_otp("654987")
        otp_record.save()

        # 2. Verify OTP -> User is automatically created without password/name prompt!
        verify_res = self.client.post(
            reverse("verify_otp"),
            data=json.dumps({"email": new_email, "otp": "654987", "purpose": "customer_login"}),
            content_type="application/json"
        )
        self.assertEqual(verify_res.status_code, 200)
        self.assertTrue(verify_res.json()["success"])

        # 3. Check created user in database
        created_user = User.objects.filter(email__iexact=new_email).first()
        self.assertIsNotNone(created_user)
        self.assertTrue(created_user.is_active)
        self.assertFalse(created_user.has_usable_password())

        # 4. Check session is authenticated
        dash_res = self.client.get(reverse("dashboard"))
        self.assertEqual(dash_res.status_code, 200)
        self.assertEqual(dash_res.context["user"], created_user)

    # -------------------------------------------------------------
    # 17. Register URL redirects cleanly to OTP login
    # -------------------------------------------------------------
    def test_17_register_url_redirects_to_otp_login(self):
        res = self.client.get(reverse("register"))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("login"))


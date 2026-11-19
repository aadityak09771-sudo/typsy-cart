from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from delivery.models import DeliveryPartner, DeliveryAssignment, OrderStatusHistory
from orders.models import Order, OrderItem
from products.models import Product

User = get_user_model()


class DeliveryPartnerModelTests(TestCase):
    """Unit tests for DeliveryPartner model fields, helper methods, and IDs."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="driver_arun",
            email="arun@tipsycart.com",
            password="DriverPassword123!"
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.user,
            full_name="Arun Kumar",
            phone="9876543210",
            email="arun@tipsycart.com",
            vehicle_type="bike",
            vehicle_number="MH 02 CZ 9988",
            service_pincodes="400001, 400002, 400003",
            availability_status="available",
            is_active=True,
        )

    def test_partner_id_auto_generation(self):
        """Delivery partner should receive an auto-generated partner_id starting with DP-"""
        self.assertTrue(self.partner.partner_id.startswith("DP-"))

    def test_partner_display_name_and_str(self):
        """String representation and display name should prefer full_name over username."""
        self.assertEqual(self.partner.get_display_name(), "Arun Kumar")
        self.assertIn("Arun Kumar", str(self.partner))
        self.assertIn(self.partner.partner_id, str(self.partner))

    def test_serves_pincode_matching(self):
        """Partner should accurately match served PIN codes."""
        self.assertTrue(self.partner.serves_pincode("400001"))
        self.assertTrue(self.partner.serves_pincode("400002"))
        self.assertFalse(self.partner.serves_pincode("400099"))

    def test_serves_pincode_wildcard(self):
        """Partner with empty PIN codes serves all PIN codes."""
        self.partner.service_pincodes = ""
        self.partner.save()
        self.assertTrue(self.partner.serves_pincode("400099"))


class DeliveryPartnerAuthenticationTests(TestCase):
    """Tests for Delivery Partner login, logout, and credential handling."""

    def setUp(self):
        self.client = Client()
        self.driver_user = User.objects.create_user(
            username="driver_vikram",
            email="vikram@tipsycart.com",
            password="DriverPass123!"
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.driver_user,
            full_name="Vikram Singh",
            phone="9876543211",
            is_active=True,
        )

        self.inactive_driver = User.objects.create_user(
            username="driver_inactive",
            email="inactive_driver@tipsycart.com",
            password="DriverPass123!"
        )
        self.inactive_partner = DeliveryPartner.objects.create(
            user=self.inactive_driver,
            full_name="Inactive Driver",
            phone="9876543212",
            is_active=False,
        )

    def test_partner_login_success(self):
        """Valid driver credentials redirect to driver dashboard."""
        response = self.client.post(
            reverse("delivery:login"),
            {"username": "driver_vikram", "password": "DriverPass123!"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertEqual(response.context["user"].username, "driver_vikram")
        self.assertContains(response, "Vikram Singh")
        self.assertContains(response, "Delivery Partner Dashboard")

    def test_partner_login_invalid_password(self):
        """Invalid driver credentials display an error message."""
        response = self.client.post(
            reverse("delivery:login"),
            {"username": "driver_vikram", "password": "WrongPassword!"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "Invalid username or password")

    def test_inactive_partner_login_rejected(self):
        """Deactivated delivery partner is rejected from logging in."""
        response = self.client.post(
            reverse("delivery:login"),
            {"username": "driver_inactive", "password": "DriverPass123!"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)
        self.assertContains(response, "deactivated")

    def test_partner_logout(self):
        """Driver logout clears the session and redirects to driver login."""
        self.client.login(username="driver_vikram", password="DriverPass123!")
        response = self.client.post(reverse("delivery:logout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["user"].is_authenticated)

    def test_partner_registration_success(self):
        """New driver can register, which creates both User and DeliveryPartner and logs them in."""
        response = self.client.post(
            reverse("delivery:register"),
            {
                "full_name": "Suresh Raina",
                "username": "suresh_driver",
                "phone": "9876543299",
                "email": "suresh@tipsycart.com",
                "vehicle_type": "bike",
                "vehicle_number": "MH 02 AA 1111",
                "service_pincodes": "400001, 400005",
                "address": "Bandra Station Road",
                "password": "SureshPassword123!",
                "confirm_password": "SureshPassword123!",
            },
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["user"].is_authenticated)
        self.assertEqual(response.context["user"].username, "suresh_driver")
        self.assertTrue(hasattr(response.context["user"], "delivery_profile"))
        partner = response.context["user"].delivery_profile
        self.assertEqual(partner.full_name, "Suresh Raina")
        self.assertEqual(partner.vehicle_type, "bike")
        self.assertEqual(partner.vehicle_number, "MH 02 AA 1111")
        self.assertTrue(partner.is_active)
        self.assertContains(response, "Suresh Raina")

    def test_partner_registration_mismatched_password(self):
        """Registration fails if passwords do not match."""
        response = self.client.post(
            reverse("delivery:register"),
            {
                "full_name": "Mismatched Pass",
                "username": "mismatch_driver",
                "phone": "9876543298",
                "vehicle_type": "bike",
                "password": "Password123!",
                "confirm_password": "DifferentPassword123!",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords do not match")
        self.assertFalse(User.objects.filter(username="mismatch_driver").exists())

    def test_partner_registration_duplicate_username(self):
        """Registration fails if username is already taken."""
        response = self.client.post(
            reverse("delivery:register"),
            {
                "full_name": "Vikram Duplicate",
                "username": "driver_vikram",  # already in setUp
                "phone": "9876543297",
                "vehicle_type": "bike",
                "password": "Password123!",
                "confirm_password": "Password123!",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already taken")

    def test_login_and_register_pages_contain_eye_toggle(self):
        """Login and register pages render password eye toggle button and togglePasswordVisibility script."""
        login_res = self.client.get(reverse("delivery:login"))
        self.assertEqual(login_res.status_code, 200)
        self.assertContains(login_res, "toggle-password-btn")
        self.assertContains(login_res, "togglePasswordVisibility")
        self.assertContains(login_res, reverse("delivery:register"))

        reg_res = self.client.get(reverse("delivery:register"))
        self.assertEqual(reg_res.status_code, 200)
        self.assertContains(reg_res, "toggle-password-btn")
        self.assertContains(reg_res, "togglePasswordVisibility")
        self.assertContains(reg_res, reverse("delivery:login"))


class RoleBasedAccessControlTests(TestCase):
    """Security tests verifying strict isolation between Customer, Partner, and Admin roles."""

    def setUp(self):
        self.client = Client()
        # Normal Customer
        self.customer = User.objects.create_user(
            username="regular_customer",
            email="cust@example.com",
            password="CustomerPass123!"
        )
        # Driver 1
        self.driver1_user = User.objects.create_user(
            username="driver_one",
            email="d1@tipsycart.com",
            password="DriverPass123!"
        )
        self.partner1 = DeliveryPartner.objects.create(
            user=self.driver1_user,
            full_name="Driver One",
            phone="9876543201",
            is_active=True,
        )
        # Driver 2
        self.driver2_user = User.objects.create_user(
            username="driver_two",
            email="d2@tipsycart.com",
            password="DriverPass123!"
        )
        self.partner2 = DeliveryPartner.objects.create(
            user=self.driver2_user,
            full_name="Driver Two",
            phone="9876543202",
            is_active=True,
        )
        # Order assigned to Driver 1
        self.order1 = Order.objects.create(
            user=self.customer,
            full_name="Customer Test",
            phone="9123456789",
            address="123 Sea View Road",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            total_amount=599.00,
            status="Assigned",
        )
        self.assignment1 = DeliveryAssignment.objects.create(
            order=self.order1,
            partner=self.partner1,
            status="Assigned",
        )

    def test_customer_cannot_access_delivery_dashboard(self):
        """Customer attempting to access /delivery/dashboard/ is redirected with error."""
        self.client.login(username="regular_customer", password="CustomerPass123!")
        response = self.client.get(reverse("delivery:dashboard"), follow=True)
        self.assertContains(response, "Access denied")
        self.assertRedirects(response, reverse("delivery:login"))

    def test_anonymous_user_redirected_to_delivery_login(self):
        """Unauthenticated visitor is redirected to /delivery/login/."""
        response = self.client.get(reverse("delivery:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("delivery:login"), response.url)

    def test_delivery_partner_cannot_access_django_admin(self):
        """Delivery partner (non-staff) cannot access /admin/."""
        self.client.login(username="driver_one", password="DriverPass123!")
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_partner_cannot_access_another_partners_order(self):
        """Driver 2 cannot view or manipulate Driver 1's assigned order."""
        self.client.login(username="driver_two", password="DriverPass123!")
        # Detail view should return 404
        response = self.client.get(reverse("delivery:order_detail", kwargs={"order_id": self.order1.id}))
        self.assertEqual(response.status_code, 404)
        # Status action on assignment 1 should return 404
        post_response = self.client.post(reverse("delivery:accept_order", kwargs={"assignment_id": self.assignment1.id}))
        self.assertEqual(post_response.status_code, 404)


class AdminOrderAssignmentWorkflowTests(TestCase):
    """Tests for Admin assigning, reassigning, and cancelling delivery assignments."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="superadmin",
            email="admin@tipsycart.com",
            password="AdminPass123!"
        )
        self.driver_user = User.objects.create_user(
            username="driver_ravi",
            email="ravi@tipsycart.com",
            password="DriverPass123!"
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.driver_user,
            full_name="Ravi Shankar",
            phone="9876543220",
            service_pincodes="400001, 400002",
            availability_status="available",
            is_active=True,
        )
        self.order = Order.objects.create(
            full_name="Rajesh Sharma",
            phone="9820012345",
            address="Flat 402, Sunshine Apts",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            total_amount=1250.00,
            status="Confirmed",
        )

    def test_admin_assign_order_workflow(self):
        """Admin selects a delivery partner and assigns the order."""
        self.client.login(username="superadmin", password="AdminPass123!")
        url = reverse("admin:orders_order_assign_delivery", args=[self.order.id])

        # Check GET shows assign delivery page with available partners
        get_res = self.client.get(url)
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, "Assign Delivery Partner")
        self.assertContains(get_res, "Ravi Shankar")

        # Post assignment
        post_res = self.client.post(url, {
            "partner_id": self.partner.id,
            "notes": "Fragile items. Handle with care.",
        }, follow=True)

        self.assertEqual(post_res.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "Assigned")

        assignment = DeliveryAssignment.objects.get(order=self.order)
        self.assertEqual(assignment.partner, self.partner)
        self.assertEqual(assignment.status, "Assigned")
        self.assertEqual(assignment.notes, "Fragile items. Handle with care.")
        self.assertEqual(assignment.assigned_by, self.admin)

        # Audit history must be recorded
        history = OrderStatusHistory.objects.filter(order=self.order).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.new_status, "Assigned")
        self.assertEqual(history.changed_by, self.admin)

    def test_admin_cancel_assignment(self):
        """Admin can cancel an active delivery assignment."""
        self.client.login(username="superadmin", password="AdminPass123!")
        assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status="Assigned",
            assigned_by=self.admin,
        )
        self.order.status = "Assigned"
        self.order.save()

        cancel_url = reverse("admin:orders_order_cancel_assignment", args=[self.order.id])
        res = self.client.post(cancel_url, follow=True)
        self.assertEqual(res.status_code, 200)

        self.order.refresh_from_db()
        assignment.refresh_from_db()
        self.assertEqual(self.order.status, "Confirmed")
        self.assertEqual(assignment.status, "Cancelled")


class DeliveryPartnerOrderLifecycleTests(TestCase):
    """Tests the full delivery lifecycle: Assigned -> Accepted -> Picked Up -> Out for Delivery -> Delivered."""

    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            username="customer_sunita",
            email="sunita@example.com",
            password="CustomerPass123!"
        )
        self.driver_user = User.objects.create_user(
            username="driver_kiran",
            email="kiran@tipsycart.com",
            password="DriverPass123!"
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.driver_user,
            full_name="Kiran Patel",
            phone="9876543230",
            vehicle_type="scooter",
            vehicle_number="MH 01 AX 7766",
            availability_status="available",
            is_active=True,
        )
        self.product = Product.objects.create(
            name="Organic Cotton Pads",
            price=299.00,
            category="Period Care",
            stock=50,
        )
        self.order = Order.objects.create(
            user=self.customer,
            full_name="Sunita Deshmukh",
            phone="9821123456",
            address="Plot 15, Green Glen Layout",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            total_amount=598.00,
            payment_method="COD",
            status="Assigned",
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=299.00,
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status="Assigned",
        )
        self.client.login(username="driver_kiran", password="DriverPass123!")

    def test_partner_accept_assignment(self):
        """Driver accepts an assigned order."""
        res = self.client.post(
            reverse("delivery:accept_order", kwargs={"assignment_id": self.assignment.id}),
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.assignment.status, "Accepted")
        self.assertEqual(self.order.status, "Accepted")
        self.assertIsNotNone(self.assignment.accepted_at)

    def test_partner_pickup_assignment(self):
        """Driver marks order as picked up from the store."""
        self.assignment.status = "Accepted"
        self.assignment.save()

        res = self.client.post(
            reverse("delivery:pickup_order", kwargs={"assignment_id": self.assignment.id}),
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.assignment.status, "Picked Up")
        self.assertEqual(self.order.status, "Picked Up")
        self.assertIsNotNone(self.assignment.picked_up_at)

    def test_partner_out_for_delivery_assignment(self):
        """Driver marks order as out for delivery."""
        self.assignment.status = "Picked Up"
        self.assignment.save()

        res = self.client.post(
            reverse("delivery:out_for_delivery", kwargs={"assignment_id": self.assignment.id}),
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.assignment.status, "Out for Delivery")
        self.assertEqual(self.order.status, "Out for Delivery")

    def test_partner_deliver_assignment(self):
        """Driver completes delivery successfully."""
        self.assignment.status = "Out for Delivery"
        self.assignment.save()

        res = self.client.post(
            reverse("delivery:deliver_order", kwargs={"assignment_id": self.assignment.id}),
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.assignment.status, "Delivered")
        self.assertEqual(self.order.status, "Delivered")
        self.assertIsNotNone(self.assignment.delivered_at)

    def test_customer_dashboard_reflects_tracking(self):
        """Customer dashboard displays assigned driver name, vehicle, and current tracking status."""
        self.assignment.status = "Out for Delivery"
        self.assignment.save()
        self.order.status = "Out for Delivery"
        self.order.save()

        cust_client = Client()
        cust_client.login(username="customer_sunita", password="CustomerPass123!")
        res = cust_client.get(reverse("dashboard"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Kiran Patel")
        self.assertContains(res, "Scooter")
        self.assertContains(res, "MH 01 AX 7766")
        self.assertContains(res, "Call Driver")


class DeliveryPartnerEdgeCasesTests(TestCase):
    """Tests for rejection, failure handling, and profile updates."""

    def setUp(self):
        self.client = Client()
        self.driver_user = User.objects.create_user(
            username="driver_amit",
            email="amit@tipsycart.com",
            password="DriverPass123!"
        )
        self.partner = DeliveryPartner.objects.create(
            user=self.driver_user,
            full_name="Amit Verma",
            phone="9876543240",
            availability_status="available",
            is_active=True,
        )
        self.order = Order.objects.create(
            full_name="Test Customer",
            phone="9820011223",
            address="12 Park Street",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            total_amount=350.00,
            status="Assigned",
        )
        self.assignment = DeliveryAssignment.objects.create(
            order=self.order,
            partner=self.partner,
            status="Assigned",
        )
        self.client.login(username="driver_amit", password="DriverPass123!")

    def test_partner_rejects_assignment_with_reason(self):
        """Driver rejects an assignment; order returns to Confirmed status for admin reassignment."""
        res = self.client.post(
            reverse("delivery:reject_order", kwargs={"assignment_id": self.assignment.id}),
            {"rejection_reason": "Vehicle puncture, unable to pick up."},
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.assignment.status, "Rejected")
        self.assertEqual(self.assignment.rejection_reason, "Vehicle puncture, unable to pick up.")
        self.assertEqual(self.order.status, "Confirmed")

    def test_partner_fails_delivery_with_reason(self):
        """Driver marks delivery as failed after pickup."""
        self.assignment.status = "Out for Delivery"
        self.assignment.save()
        self.order.status = "Out for Delivery"
        self.order.save()

        res = self.client.post(
            reverse("delivery:fail_delivery", kwargs={"assignment_id": self.assignment.id}),
            {"failure_reason": "Customer unreachable, house locked."},
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.assignment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.assignment.status, "Delivery Failed")
        self.assertEqual(self.assignment.failure_reason, "Customer unreachable, house locked.")
        self.assertEqual(self.order.status, "Delivery Failed")

    def test_partner_profile_update(self):
        """Partner updates availability and vehicle details."""
        res = self.client.post(
            reverse("delivery:profile"),
            {
                "phone": "9876500000",
                "address": "New Hub Location, Andheri West",
                "vehicle_type": "car",
                "vehicle_number": "MH 02 EE 1122",
                "availability_status": "busy",
            },
            follow=True
        )
        self.assertEqual(res.status_code, 200)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.phone, "9876500000")
        self.assertEqual(self.partner.vehicle_type, "car")
        self.assertEqual(self.partner.vehicle_number, "MH 02 EE 1122")
        self.assertEqual(self.partner.availability_status, "busy")

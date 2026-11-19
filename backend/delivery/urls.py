from django.urls import path
from . import views

app_name = "delivery"

urlpatterns = [
    # Authentication
    path("login/", views.partner_login, name="login"),
    path("register/", views.partner_register, name="register"),
    path("logout/", views.partner_logout, name="logout"),

    # Partner Dashboard & Profile
    path("dashboard/", views.partner_dashboard, name="dashboard"),
    path("profile/", views.partner_profile, name="profile"),

    # Order details
    path("orders/<int:order_id>/", views.partner_order_detail, name="order_detail"),

    # Status workflow actions
    path("assignment/<int:assignment_id>/accept/", views.accept_assignment, name="accept_order"),
    path("assignment/<int:assignment_id>/reject/", views.reject_assignment, name="reject_order"),
    path("assignment/<int:assignment_id>/pickup/", views.pickup_assignment, name="pickup_order"),
    path("assignment/<int:assignment_id>/out-for-delivery/", views.out_for_delivery_assignment, name="out_for_delivery"),
    path("assignment/<int:assignment_id>/deliver/", views.deliver_assignment, name="deliver_order"),
    path("assignment/<int:assignment_id>/fail/", views.fail_assignment, name="fail_delivery"),
]

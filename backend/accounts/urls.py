
from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Existing website routes
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),

    # Mobile app authentication APIs
    path("api/register/", api_views.RegisterAPIView.as_view(), name="api_register"),
    path("api/login/", api_views.LoginAPIView.as_view(), name="api_login"),
    path("api/logout/", api_views.LogoutAPIView.as_view(), name="api_logout"),
    path("api/profile/", api_views.ProfileAPIView.as_view(), name="api_profile"),
    path("api/my-orders/", api_views.MyOrdersAPIView.as_view(), name="api_my_orders"),

     # Push notification device registration
    path("api/push-token/", api_views.PushDeviceAPIView.as_view(), name="api_push_token"),

]


from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token

from orders.models import Order
from .models import PushDevice

User = get_user_model()


class RegisterAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = str(request.data.get("username") or "").strip()
        email = str(request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""

        if not username or not email or not password:
            return Response(
                {
                    "success": False,
                    "message": "Username, email and password are required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(password) < 8:
            return Response(
                {
                    "success": False,
                    "message": "Password must contain at least 8 characters."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username__iexact=username).exists():
            return Response(
                {"success": False, "message": "Username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"success": False, "message": "Email already registered."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )

            token, _ = Token.objects.get_or_create(user=user)

            return Response(
                {
                    "success": True,
                    "message": "Account created successfully.",
                    "token": token.key,
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except IntegrityError:
            return Response(
                {
                    "success": False,
                    "message": "Could not create account. Please try again."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class LoginAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = str(request.data.get("username") or "").strip()
        password = request.data.get("password") or ""

        if not username or not password:
            return Response(
                {
                    "success": False,
                    "message": "Username and password are required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request=request,
            username=username,
            password=password,
        )

        if user is None:
            return Response(
                {
                    "success": False,
                    "message": "Invalid username or password."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "success": True,
                "message": "Login successful.",
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            },
            status=status.HTTP_200_OK,
        )


class LogoutAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()

        return Response(
            {
                "success": True,
                "message": "Logout successful."
            },
            status=status.HTTP_200_OK,
        )


class ProfileAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        return Response(
            {
                "success": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            },
            status=status.HTTP_200_OK,
        )


class MyOrdersAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            Order.objects
            .filter(user=request.user)
            .prefetch_related("items")
            .order_by("-created_at")
        )

        order_data = []

        for order in orders:
            items_data = []

            for item in order.items.all():
                items_data.append({
                    "product_name": item.product_name,
                    "price": str(item.price),
                    "quantity": item.quantity,
                    "subtotal": str(item.price * item.quantity),
                })

            order_data.append({
                "id": order.id,
                "total_amount": str(order.total_amount),
                "status": order.status,
                "payment_method": order.payment_method,
                "created_at": order.created_at.isoformat(),
                "full_name": order.full_name,
                "phone": order.phone,
                "address": order.address,
                "city": order.city,
                "state": order.state,
                "pincode": order.pincode,
                "items": items_data,
            })

        return Response(
            {
                "success": True,
                "total_orders": len(order_data),
                "orders": order_data,
            },
            status=status.HTTP_200_OK,
        )


class PushDeviceAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        expo_push_token = str(
            request.data.get("expo_push_token") or ""
        ).strip()

        platform = str(
            request.data.get("platform") or ""
        ).strip().lower()

        if not expo_push_token:
            return Response(
                {
                    "success": False,
                    "message": "Expo push token is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(expo_push_token) > 255:
            return Response(
                {
                    "success": False,
                    "message": "Invalid Expo push token."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if platform not in ("android", "ios"):
            return Response(
                {
                    "success": False,
                    "message": "Platform must be android or ios."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            device, created = PushDevice.objects.update_or_create(
                expo_push_token=expo_push_token,
                defaults={
                    "user": request.user,
                    "platform": platform,
                },
            )

            return Response(
                {
                    "success": True,
                    "message": "Push device registered successfully.",
                    "created": created,
                },
                status=status.HTTP_200_OK,
            )

        except IntegrityError:
            return Response(
                {
                    "success": False,
                    "message": "Could not register this device."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

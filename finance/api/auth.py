"""JWT authentication endpoints.

Web client (``/api/v1/auth/login|refresh|logout/``): the access token is
returned in the response body and kept in memory by the frontend; the refresh
token lives only in an HttpOnly cookie scoped to ``/api/v1/auth/``.

Mobile client (``/api/v1/auth/token/...``): standard SimpleJWT views, both
tokens are sent in the response body.
"""

from django.conf import settings
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)

from finance.api.serializers import UserSerializer


def _set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds()),
        path=settings.JWT_REFRESH_COOKIE_PATH,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )


def _delete_refresh_cookie(response):
    response.delete_cookie(
        settings.JWT_REFRESH_COOKIE_NAME,
        path=settings.JWT_REFRESH_COOKIE_PATH,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
    )


class AuthThrottleMixin:
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "auth"


class CookieAuthView(AuthThrottleMixin, APIView):
    # Credentials come from the body or the refresh cookie, never the session,
    # so no session/CSRF authentication is applied here.
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get_authenticate_header(self, request):
        # Without authentication classes DRF would turn 401 into 403.
        return 'Bearer realm="api"'


access_response = inline_serializer(
    "AccessTokenResponse",
    {"access": serializers.CharField(), "user": UserSerializer()},
)


class WebLoginView(CookieAuthView):
    @extend_schema(request=TokenObtainPairSerializer, responses=access_response)
    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as error:
            raise InvalidToken(error.args[0]) from error

        response = Response(
            {
                "access": serializer.validated_data["access"],
                "user": UserSerializer(serializer.user).data,
            }
        )
        _set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


class WebRefreshView(CookieAuthView):
    @extend_schema(
        request=None,
        responses=inline_serializer(
            "AccessTokenOnlyResponse", {"access": serializers.CharField()}
        ),
    )
    def post(self, request):
        refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if not refresh:
            raise InvalidToken("Refresh token cookie is missing.")

        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as error:
            response = Response(
                {"detail": str(error), "code": "token_not_valid"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _delete_refresh_cookie(response)
            return response

        response = Response({"access": serializer.validated_data["access"]})
        if "refresh" in serializer.validated_data:
            _set_refresh_cookie(response, serializer.validated_data["refresh"])
        return response


class WebLogoutView(CookieAuthView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # Already invalid or expired: nothing left to revoke.

        response = Response(status=status.HTTP_204_NO_CONTENT)
        _delete_refresh_cookie(response)
        return response


class MobileTokenObtainView(AuthThrottleMixin, TokenObtainPairView):
    pass


class MobileTokenRefreshView(AuthThrottleMixin, TokenRefreshView):
    pass


class MobileTokenBlacklistView(AuthThrottleMixin, TokenBlacklistView):
    pass


class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

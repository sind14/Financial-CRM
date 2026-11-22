from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from finance.api import auth
from finance.api.views import (
    ClientViewSet,
    MonthlyExpenseViewSet,
    PaymentServiceViewSet,
    PaymentViewSet,
    StatisticsView,
)

app_name = "api"

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payment")
router.register("payment-services", PaymentServiceViewSet, basename="payment-service")
router.register("monthly-expenses", MonthlyExpenseViewSet, basename="monthly-expense")
router.register("clients", ClientViewSet, basename="client")

auth_urlpatterns = [
    path("login/", auth.WebLoginView.as_view(), name="login"),
    path("refresh/", auth.WebRefreshView.as_view(), name="refresh"),
    path("logout/", auth.WebLogoutView.as_view(), name="logout"),
    path("token/", auth.MobileTokenObtainView.as_view(), name="token"),
    path(
        "token/refresh/",
        auth.MobileTokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "token/blacklist/",
        auth.MobileTokenBlacklistView.as_view(),
        name="token-blacklist",
    ),
    path("me/", auth.MeView.as_view(), name="me"),
]

urlpatterns = [
    path("auth/", include((auth_urlpatterns, "auth"))),
    path("statistics/", StatisticsView.as_view(), name="statistics"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    path("", include(router.urls)),
]

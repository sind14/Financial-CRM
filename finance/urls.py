from django.urls import path
from finance.views import PaymentListCreateView


urlpatterns = [
    path("payments/", PaymentListCreateView.as_view(), name="payment-list-create"),
]

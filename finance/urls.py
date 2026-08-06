from django.urls import path

from finance.views import PaymentListCreateView, monthly_summary_view


urlpatterns = [
    path("payments/", PaymentListCreateView.as_view(), name="payment-list-create"),
    path("monthly-summary/", monthly_summary_view, name="monthly-summary"),
]

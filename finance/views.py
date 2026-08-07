from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from finance.models import Payment
from finance.serializers import PaymentSerializer


class PaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(owner=self.request.user).order_by("-date", "-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@api_view(["GET"])
def monthly_summary_view(request):
    today = timezone.localdate()

    try:
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))
    except ValueError:
        return Response(
            {"detail": "Year and month must be numbers."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not 1 <= month <= 12:
        return Response(
            {"detail": "Month must be between 1 and 12."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payments = Payment.objects.filter(
        owner=request.user,
        date__year=year,
        date__month=month,
    )

    def total_payments(payment_type):
        return payments.filter(payment_type=payment_type).aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00"))
        )["total"]

    income = total_payments(Payment.PaymentType.INCOME)
    expense = total_payments(Payment.PaymentType.EXPENSE)
    balance = income - expense

    return Response(
        {
            "year": year,
            "month": month,
            "income": str(income),
            "expense": str(expense),
            "balance": str(balance),
        }
    )

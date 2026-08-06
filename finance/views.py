from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import generics
from rest_framework.decorators import api_view
from rest_framework.response import Response

from finance.models import Payment
from finance.serializers import PaymentSerializer


class PaymentListCreateView(generics.ListCreateAPIView):
    queryset = Payment.objects.all().order_by("-date", "-created_at")
    serializer_class = PaymentSerializer


@api_view(["GET"])
def monthly_summary_view(request):
    today = timezone.localdate()

    year = int(request.query_params.get("year", today.year))
    month = int(request.query_params.get("month", today.month))

    payments = Payment.objects.filter(
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

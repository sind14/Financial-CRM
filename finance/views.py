from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from finance.forms import MonthlyExpenseForm, PaymentForm
from finance.models import Client, MonthlyExpense, Payment
from finance.serializers import ClientSerializer, PaymentSerializer


def _get_monthly_summary(user, year, month):
    payments = Payment.objects.filter(
        owner=user,
        date__year=year,
        date__month=month,
    )

    def total_payments(payment_type):
        return payments.filter(payment_type=payment_type).aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00"))
        )["total"]

    income = total_payments(Payment.PaymentType.INCOME)
    expense = total_payments(Payment.PaymentType.EXPENSE)

    return {
        "income": income,
        "expense": expense,
        "balance": income - expense,
    }


class PaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(owner=self.request.user).order_by(
            "-date", "-created_at"
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ClientListCreateView(generics.ListCreateAPIView):
    serializer_class = ClientSerializer

    def get_queryset(self):
        return Client.objects.filter(owner=self.request.user)

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

    summary = _get_monthly_summary(request.user, year, month)

    return Response(
        {
            "year": year,
            "month": month,
            "income": str(summary["income"]),
            "expense": str(summary["expense"]),
            "balance": str(summary["balance"]),
        }
    )


@login_required
def dashboard_view(request):
    today = timezone.localdate()

    summary = _get_monthly_summary(
        request.user,
        today.year,
        today.month,
    )

    cards = [
        ("Income", summary["income"]),
        ("Expenses", summary["expense"]),
        ("Balance", summary["balance"]),
    ]

    return render(
        request,
        "finance/dashboard.html",
        {"cards": cards},
    )


@login_required
def payments_view(request):
    payments = Payment.objects.filter(
        owner=request.user,
    ).order_by("-date", "-created_at")

    if request.method == "POST":
        form = PaymentForm(request.POST, user=request.user)

        if form.is_valid():
            payment = form.save(commit=False)
            payment.owner = request.user
            payment.save()

            return redirect("payments")

    else:
        form = PaymentForm(user=request.user)

    return render(
        request,
        "finance/payments.html",
        {
            "payments": payments,
            "form": form,
        },
    )


@login_required
def payment_edit_view(request, pk):
    payment = get_object_or_404(Payment, pk=pk, owner=request.user)
    if request.method == "POST":
        form = PaymentForm(request.POST, instance=payment, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("payments")

    else:
        form = PaymentForm(instance=payment, user=request.user)

    return render(
        request,
        "finance/payment_form.html",
        {
            "form": form,
            "title": "Edit Payment",
        },
    )


@login_required
def payment_delete_view(request, pk):
    payment = get_object_or_404(Payment, pk=pk, owner=request.user)
    if request.method == "POST":
        payment.delete()
        return redirect("payments")

    return render(
        request,
        "finance/payment_delete.html",
        {"payment": payment},
    )


@login_required
def monthly_expenses_view(request):
    expenses = MonthlyExpense.objects.filter(owner=request.user).order_by("-created_at")

    if request.method == "POST":
        form = MonthlyExpenseForm(request.POST)

        if form.is_valid():
            expense = form.save(commit=False)
            expense.owner = request.user
            expense.save()

            return redirect("monthly-expenses")
    else:
        form = MonthlyExpenseForm()

    return render(
        request,
        "finance/monthly_expenses.html",
        {
            "expenses": expenses,
            "form": form,
        },
    )


@login_required
def monthly_expense_edit_view(request, pk):
    expense = get_object_or_404(
        MonthlyExpense,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        form = MonthlyExpenseForm(request.POST, instance=expense)

        if form.is_valid():
            form.save()
            return redirect("monthly-expenses")
    else:
        form = MonthlyExpenseForm(instance=expense)

    return render(
        request,
        "finance/monthly_expense_edit.html",
        {"form": form},
    )


@login_required
def monthly_expense_delete_view(request, pk):
    expense = get_object_or_404(
        MonthlyExpense,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        expense.delete()
        return redirect("monthly-expenses")

    return render(
        request,
        "finance/monthly_expense_delete.html",
        {"expense": expense},
    )

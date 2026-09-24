from decimal import Decimal
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from finance.forms import MonthlyExpenseForm, PaymentForm, ClientForm
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
def statistics_view(request):
    payments = Payment.objects.filter(
        owner=request.user,
    )

    total_income = payments.filter(
        payment_type=Payment.PaymentType.INCOME,
    ).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"))
    )["total"]

    total_expenses = payments.filter(
        payment_type=Payment.PaymentType.EXPENSE,
    ).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"))
    )["total"]

    total_profit = total_income - total_expenses

    today = timezone.localdate()

    current_month_summary = _get_monthly_summary(
        request.user,
        today.year,
        today.month,
    )

    monthly_income = current_month_summary["income"]
    monthly_expenses = current_month_summary["expense"]
    monthly_profit = current_month_summary["balance"]

    monthly_statistics = []

    months = payments.dates("date", "month", order="DESC")

    for month_date in months:
        summary = _get_monthly_summary(
            request.user,
            month_date.year,
            month_date.month,
        )

        monthly_statistics.append({
            "year": month_date.year,
            "month": date_format(month_date, "F"),
            "income": summary["income"],
            "expenses": summary["expense"],
            "profit": summary["balance"],
        })

    return render(
        request,
        "finance/statistics.html",
        {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total_profit": total_profit,

            "monthly_income": monthly_income,
            "monthly_expenses": monthly_expenses,
            "monthly_profit": monthly_profit,

            "monthly_statistics": monthly_statistics,
        },
    )


@login_required
def payments_view(request):
    payments = Payment.objects.filter(
        owner=request.user,
    ).order_by("-date", "-created_at")

    return render(
        request,
        "finance/payments.html",
        {"payments": payments},
    )


@login_required
def payment_add_view(request):
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
        "finance/payment_form.html",
        {
            "form": form,
            "title": _("New Payment"),
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
            "title": _("Edit Payment"),
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
        "finance/confirm_delete.html",
        {
            "object": f"{payment.amount} — {payment.category}",
            "cancel_url": "payments",
        },
    )


@login_required
def monthly_expenses_view(request):
    monthly_expenses = MonthlyExpense.objects.filter(
        owner=request.user,
    ).order_by("-amount")

    return render(
        request,
        "finance/monthly_expenses.html",
        {"monthly_expenses": monthly_expenses},
    )


@login_required
def monthly_expense_detail_view(request, pk):
    monthly_expense = get_object_or_404(
        MonthlyExpense,
        pk=pk,
        owner=request.user,
    )

    return render(
        request,
        "finance/monthly_expense_detail.html",
        {"monthly_expense": monthly_expense},
    )


@login_required
def monthly_expense_add_view(request):
    if request.method == "POST":
        form = MonthlyExpenseForm(request.POST)

        if form.is_valid():
            monthly_expense = form.save(commit=False)
            monthly_expense.owner = request.user
            monthly_expense.save()

            first_day_of_month = timezone.localdate().replace(day=1)

            Payment.objects.get_or_create(
                monthly_expense=monthly_expense,
                date=first_day_of_month,
                defaults={
                    "amount": monthly_expense.amount,
                    "payment_type": Payment.PaymentType.EXPENSE,
                    "category": monthly_expense.name,
                    "description": "Monthly Expense",
                    "owner": request.user,
                },
            )

            return redirect("monthly-expenses")

    else:
        form = MonthlyExpenseForm()

    return render(
        request,
        "finance/monthly_expense_form.html",
        {
            "form": form,
            "title": _("New Monthly Expense"),
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
            expense = form.save()

            first_day_of_month = timezone.localdate().replace(day=1)

            Payment.objects.filter(
                monthly_expense=expense,
                date=first_day_of_month,
                owner=request.user,
            ).update(
                amount=expense.amount,
                category=expense.name,
            )

            return redirect("monthly-expenses")

    else:
        form = MonthlyExpenseForm(instance=expense)

    return render(
        request,
        "finance/monthly_expense_form.html",
        {
            "form": form,
            "title": _("Edit Monthly Expense"),
        },
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
        "finance/confirm_delete.html",
        {
            "object": expense,
            "cancel_url": "monthly-expenses",
        },
    )


@login_required
def clients_view(request):
    clients = Client.objects.filter(
        owner=request.user
    ).order_by("surname", "name")

    form = ClientForm()

    return render(
        request,
        "finance/clients.html",
        {
            "clients": clients,
            "form": form,
        },
    )


@login_required
def client_add_view(request):
    if request.method == "POST":
        form = ClientForm(request.POST)

        if form.is_valid():
            client = form.save(commit=False)
            client.owner = request.user
            client.save()

            return redirect("clients")

    else:
        form = ClientForm()

    return render(
        request,
        "finance/client_form.html",
        {
            "title": _("New Client"),
            "form": form,
        },
    )


@login_required
def client_detail_view(request, pk):
    client = get_object_or_404(Client, pk=pk, owner=request.user)

    payments = Payment.objects.filter(
        owner=request.user,
        client=client,
        payment_type=Payment.PaymentType.INCOME,
    ).order_by("-date", "-created_at")

    return render(
        request,
        "finance/client_detail.html",
        {
            "client": client,
            "payments": payments,
        },
    )


@login_required
def client_edit_view(request, pk):
    client = get_object_or_404(Client, pk=pk, owner=request.user)

    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)

        if form.is_valid():
            form.save()
            return redirect("clients")

    else:
        form = ClientForm(instance=client)

    return render(
        request,
        "finance/client_form.html",
        {
            "form": form,
            "client": client,
            "title": _("Edit Client"),
        },
    )


@login_required
def client_delete_view(request, pk):
    client = get_object_or_404(Client, pk=pk, owner=request.user)

    if request.method == "POST":
        client.delete()
        return redirect("clients")

    return render(
        request,
        "finance/confirm_delete.html",
        {
            "object": client,
            "cancel_url": "clients",
        },
    )

from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from finance.forms import (
    ClientForm,
    MonthlyExpenseForm,
    PaymentForm,
    PaymentServiceForm,
)
from finance.models import Client, MonthlyExpense, Payment, PaymentService


def _get_payment_summary(payments):
    summary = payments.aggregate(
        income=Coalesce(
            Sum(
                "amount",
                filter=Q(payment_type=Payment.PaymentType.INCOME),
            ),
            Decimal("0.00"),
        ),
        expense=Coalesce(
            Sum(
                "amount",
                filter=Q(payment_type=Payment.PaymentType.EXPENSE),
            ),
            Decimal("0.00"),
        ),
        unique_clients=Count(
            "client_id",
            filter=Q(
                payment_type=Payment.PaymentType.INCOME,
                client__isnull=False,
            ),
            distinct=True,
        ),
        procedures_count=Count(
            "pk",
            filter=Q(
                payment_type=Payment.PaymentType.INCOME,
                client__isnull=False,
            ),
        ),
    )

    return {
        **summary,
        "profit": summary["income"] - summary["expense"],
    }


def _get_monthly_summary(user, year, month):
    return _get_payment_summary(
        Payment.objects.filter(
            owner=user,
            date__year=year,
            date__month=month,
        )
    )


def _get_monthly_client_statistics(user, year, month):
    first_day_of_month = date(year, month, 1)

    if month == 12:
        first_day_of_next_month = date(year + 1, 1, 1)
    else:
        first_day_of_next_month = date(year, month + 1, 1)

    first_visit_subquery = (
        Payment.objects.filter(
            owner=user,
            client=OuterRef("pk"),
            payment_type=Payment.PaymentType.INCOME,
        )
        .order_by(
            "date",
            "created_at",
        )
        .values("date")[:1]
    )

    clients = (
        Client.objects.filter(
            owner=user,
            payments__owner=user,
            payments__payment_type=Payment.PaymentType.INCOME,
            payments__date__gte=first_day_of_month,
            payments__date__lt=first_day_of_next_month,
        )
        .annotate(
            first_visit=Subquery(first_visit_subquery),
        )
        .distinct()
    )

    return clients.aggregate(
        unique_clients=Count("pk"),
        new_clients=Count(
            "pk",
            filter=Q(first_visit__gte=first_day_of_month),
        ),
        returning_clients=Count(
            "pk",
            filter=Q(first_visit__lt=first_day_of_month),
        ),
    )


@login_required
def statistics_view(request):
    payments = Payment.objects.filter(
        owner=request.user,
    )

    total_summary = _get_payment_summary(payments)

    today = timezone.localdate()

    current_month_summary = _get_monthly_summary(
        request.user,
        today.year,
        today.month,
    )

    current_month_client_statistics = _get_monthly_client_statistics(
        request.user,
        today.year,
        today.month,
    )

    total_clients = Client.objects.filter(
        owner=request.user,
    ).count()

    monthly_statistics = []
    months = payments.dates("date", "month", order="DESC")

    for month_date in months:
        if month_date.year == today.year and month_date.month == today.month:
            summary = current_month_summary
            client_statistics = current_month_client_statistics
        else:
            summary = _get_monthly_summary(
                request.user,
                month_date.year,
                month_date.month,
            )
            client_statistics = _get_monthly_client_statistics(
                request.user,
                month_date.year,
                month_date.month,
            )

        monthly_statistics.append(
            {
                "year": month_date.year,
                "month": date_format(month_date, "F"),
                "income": summary["income"],
                "expense": summary["expense"],
                "profit": summary["profit"],
                "unique_clients": client_statistics["unique_clients"],
                "procedures_count": summary["procedures_count"],
                "new_clients": client_statistics["new_clients"],
                "returning_clients": client_statistics["returning_clients"],
            }
        )

    return render(
        request,
        "finance/statistics.html",
        {
            "total_income": total_summary["income"],
            "total_expenses": total_summary["expense"],
            "total_profit": total_summary["profit"],
            "monthly_income": current_month_summary["income"],
            "monthly_expenses": current_month_summary["expense"],
            "monthly_profit": current_month_summary["profit"],
            "total_clients": total_clients,
            "total_procedures": total_summary["procedures_count"],
            "new_clients_this_month": current_month_client_statistics["new_clients"],
            "returning_clients_this_month": current_month_client_statistics[
                "returning_clients"
            ],
            "monthly_statistics": monthly_statistics,
        },
    )


@login_required
def payments_view(request):
    payments = (
        Payment.objects.filter(owner=request.user)
        .select_related("client")
        .order_by("-date", "-created_at")
    )

    return render(
        request,
        "finance/payments.html",
        {"payments": payments},
    )


@login_required
def client_search_view(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"clients": []})

    words = query.split()

    clients = Client.objects.filter(
        owner=request.user,
    )

    for word in words:
        clients = clients.filter(
            Q(name__icontains=word)
            | Q(surname__icontains=word)
            | Q(phone__icontains=word)
        )

    clients = clients.order_by(
        "surname",
        "name",
    )[:10]

    return JsonResponse(
        {
            "clients": [
                {
                    "id": client.id,
                    "name": client.name,
                    "surname": client.surname,
                    "phone": client.phone or "",
                }
                for client in clients
            ]
        }
    )


@login_required
def client_create_ajax_view(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "POST request required."},
            status=405,
        )

    form = ClientForm(request.POST)

    if not form.is_valid():
        return JsonResponse(
            {"errors": form.errors},
            status=400,
        )

    client = form.save(commit=False)
    client.owner = request.user
    client.save()

    return JsonResponse(
        {
            "id": client.id,
            "name": client.name,
            "surname": client.surname,
            "phone": client.phone or "",
        }
    )


@login_required
def payment_add_view(request):
    if request.method == "POST":
        form = PaymentForm(request.POST, user=request.user)

        if form.is_valid():
            payment = form.save(commit=False)
            payment.owner = request.user

            payment.service = (
                payment.service_option.name if payment.service_option else ""
            )

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
            payment = form.save(commit=False)

            payment.service = (
                payment.service_option.name if payment.service_option else ""
            )

            payment.save()

            return redirect("payments")

    else:
        form = PaymentForm(instance=payment, user=request.user)

    return render(
        request,
        "finance/payment_form.html",
        {
            "form": form,
            "payment": payment,
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
            "object": f"{payment.amount} — {payment.service}",
            "cancel_url": "payments",
        },
    )


@login_required
def payment_services_view(request):
    services = PaymentService.objects.filter(
        owner=request.user,
    ).order_by("name")

    return render(
        request,
        "finance/payment_services.html",
        {
            "services": services,
        },
    )


@login_required
def payment_service_add_view(request):
    if request.method == "POST":
        form = PaymentServiceForm(request.POST)

        if form.is_valid():
            service = form.save(commit=False)
            service.owner = request.user
            service.save()

    return redirect("payment-services")


@login_required
def payment_service_edit_view(request, pk):
    service = get_object_or_404(
        PaymentService,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        form = PaymentServiceForm(request.POST, instance=service)

        if form.is_valid():
            form.save()

    return redirect("payment-services")


@login_required
def payment_service_delete_view(request, pk):
    service = get_object_or_404(
        PaymentService,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        service.delete()
        return redirect("payment-services")

    return render(
        request,
        "finance/confirm_delete.html",
        {
            "object": service,
            "cancel_url": "payment-services",
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
                    "service": monthly_expense.name,
                    "description": "Monthly Expense",
                    "owner": request.user,
                },
            )

    return redirect("monthly-expenses")


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
                service=expense.name,
            )

    return redirect("monthly-expenses")


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
    clients = (
        Client.objects.filter(owner=request.user)
        .annotate(
            visits_count=Count(
                "payments",
                filter=Q(
                    payments__owner=request.user,
                    payments__payment_type=Payment.PaymentType.INCOME,
                ),
            ),
            last_visit=Max(
                "payments__date",
                filter=Q(
                    payments__owner=request.user,
                    payments__payment_type=Payment.PaymentType.INCOME,
                ),
            ),
            total_spent=Coalesce(
                Sum(
                    "payments__amount",
                    filter=Q(
                        payments__owner=request.user,
                        payments__payment_type=Payment.PaymentType.INCOME,
                    ),
                ),
                Decimal("0.00"),
            ),
        )
        .order_by("surname", "name")
    )

    return render(
        request,
        "finance/clients.html",
        {
            "clients": clients,
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


@login_required
def client_detail_view(request, pk):
    client = get_object_or_404(
        Client,
        pk=pk,
        owner=request.user,
    )

    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)

        if form.is_valid():
            form.save()
            return redirect("client-detail", pk=client.pk)
    else:
        form = ClientForm(instance=client)

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
            "form": form,
            "payments": payments,
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

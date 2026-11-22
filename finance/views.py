from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from finance import services
from finance.forms import (
    ClientForm,
    MonthlyExpenseForm,
    PaymentForm,
    PaymentServiceForm,
)
from finance.models import Client, MonthlyExpense, Payment, PaymentService


@login_required
def statistics_view(request):
    statistics = services.get_statistics(request.user)
    total = statistics["total"]
    current_month = statistics["current_month"]

    monthly_statistics = [
        {
            **{key: value for key, value in item.items() if key != "month_date"},
            "year": item["month_date"].year,
            "month": date_format(item["month_date"], "F"),
        }
        for item in statistics["monthly"]
    ]

    return render(
        request,
        "finance/statistics.html",
        {
            "total_income": total["income"],
            "total_expenses": total["expense"],
            "total_profit": total["profit"],
            "monthly_income": current_month["income"],
            "monthly_expenses": current_month["expense"],
            "monthly_profit": current_month["profit"],
            "total_clients": total["clients"],
            "total_procedures": total["procedures"],
            "new_clients_this_month": current_month["new_clients"],
            "returning_clients_this_month": current_month["returning_clients"],
            "monthly_statistics": monthly_statistics,
        },
    )


@login_required
def payments_view(request):
    payments = services.get_user_payments(request.user)

    return render(
        request,
        "finance/payments.html",
        {"payments": payments},
    )


@login_required
def client_search_view(request):
    query = request.GET.get("q", "").strip()

    clients = services.search_clients(request.user, query)

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

            services.save_payment(payment)

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

            services.save_payment(payment)

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
    return render(
        request,
        "finance/payment_services.html",
        {
            "services": services.get_user_payment_services(request.user),
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
    monthly_expenses = services.get_user_monthly_expenses(request.user)

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
            services.create_monthly_expense(
                form.save(commit=False),
                owner=request.user,
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
            services.update_monthly_expense(form.save(commit=False))

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
    clients = services.get_user_clients_with_stats(request.user)

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

    payments = services.get_client_income_payments(request.user, client)

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

"""Business logic shared by the HTML views and the REST API.

Every function that reads data takes the user explicitly and only returns
records owned by that user.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Count, Max, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from finance.models import Client, MonthlyExpense, Payment, PaymentService

CLIENT_SEARCH_LIMIT = 10
# Used for every new payment generated from a monthly expense (web, API and
# the generate_monthly_expenses command). Existing rows are left unchanged.
MONTHLY_EXPENSE_DESCRIPTION = "Автоматично створена щомісячна витрата"


# --- Owner-scoped querysets -------------------------------------------------


def get_user_payments(user):
    return (
        Payment.objects.filter(owner=user)
        .select_related("client", "service_option")
        .order_by("-date", "-created_at")
    )


def get_user_payment_services(user):
    return PaymentService.objects.filter(owner=user).order_by("name")


def get_user_monthly_expenses(user):
    return MonthlyExpense.objects.filter(owner=user).order_by("-amount")


def get_user_clients(user):
    return Client.objects.filter(owner=user).order_by("surname", "name")


def get_user_clients_with_stats(user):
    income_filter = Q(
        payments__owner=user,
        payments__payment_type=Payment.PaymentType.INCOME,
    )

    return get_user_clients(user).annotate(
        visits_count=Count("payments", filter=income_filter),
        last_visit=Max("payments__date", filter=income_filter),
        total_spent=Coalesce(
            Sum("payments__amount", filter=income_filter),
            Decimal("0.00"),
        ),
    )


def get_client_income_payments(user, client):
    return Payment.objects.filter(
        owner=user,
        client=client,
        payment_type=Payment.PaymentType.INCOME,
    ).order_by("-date", "-created_at")


def search_clients(user, query, limit=CLIENT_SEARCH_LIMIT):
    words = query.split()

    if not words:
        return Client.objects.none()

    clients = Client.objects.filter(owner=user)

    for word in words:
        clients = clients.filter(
            Q(name__icontains=word)
            | Q(surname__icontains=word)
            | Q(phone__icontains=word)
        )

    return clients.order_by("surname", "name")[:limit]


# --- Writes -----------------------------------------------------------------


def save_payment(payment):
    """Save a payment, keeping the denormalized `service` name in sync."""
    payment.service = payment.service_option.name if payment.service_option else ""
    payment.save()
    return payment


def _first_day_of_current_month():
    return timezone.localdate().replace(day=1)


def ensure_monthly_expense_payment(monthly_expense):
    """Create this month's expense payment for a monthly expense if missing."""
    return Payment.objects.get_or_create(
        monthly_expense=monthly_expense,
        date=_first_day_of_current_month(),
        defaults={
            "amount": monthly_expense.amount,
            "payment_type": Payment.PaymentType.EXPENSE,
            "service": monthly_expense.name,
            "description": MONTHLY_EXPENSE_DESCRIPTION,
            "owner": monthly_expense.owner,
        },
    )


def create_monthly_expense(monthly_expense, owner):
    monthly_expense.owner = owner
    monthly_expense.save()
    ensure_monthly_expense_payment(monthly_expense)
    return monthly_expense


def update_monthly_expense(monthly_expense):
    """Save a monthly expense and update this month's payment to match."""
    monthly_expense.save()

    Payment.objects.filter(
        monthly_expense=monthly_expense,
        date=_first_day_of_current_month(),
        owner=monthly_expense.owner,
    ).update(
        amount=monthly_expense.amount,
        service=monthly_expense.name,
    )

    return monthly_expense


# --- Statistics -------------------------------------------------------------


def get_payment_summary(payments):
    summary = payments.aggregate(
        income=Coalesce(
            Sum("amount", filter=Q(payment_type=Payment.PaymentType.INCOME)),
            Decimal("0.00"),
        ),
        expense=Coalesce(
            Sum("amount", filter=Q(payment_type=Payment.PaymentType.EXPENSE)),
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


def get_monthly_summary(user, year, month):
    return get_payment_summary(
        Payment.objects.filter(
            owner=user,
            date__year=year,
            date__month=month,
        )
    )


def get_monthly_client_statistics(user, year, month):
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
        .order_by("date", "created_at")
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
        .annotate(first_visit=Subquery(first_visit_subquery))
        .distinct()
    )

    return clients.aggregate(
        unique_clients=Count("pk"),
        new_clients=Count("pk", filter=Q(first_visit__gte=first_day_of_month)),
        returning_clients=Count("pk", filter=Q(first_visit__lt=first_day_of_month)),
    )


def get_statistics(user):
    """Totals, current month figures and a per-month breakdown (newest first).

    Each item of `monthly` carries `month_date` (first day of that month), so
    callers can format the month name themselves.
    """
    payments = Payment.objects.filter(owner=user)
    total_summary = get_payment_summary(payments)

    today = timezone.localdate()
    current_month_summary = get_monthly_summary(user, today.year, today.month)
    current_month_clients = get_monthly_client_statistics(user, today.year, today.month)

    monthly = []

    for month_date in payments.dates("date", "month", order="DESC"):
        if month_date.year == today.year and month_date.month == today.month:
            summary = current_month_summary
            client_statistics = current_month_clients
        else:
            summary = get_monthly_summary(user, month_date.year, month_date.month)
            client_statistics = get_monthly_client_statistics(
                user, month_date.year, month_date.month
            )

        monthly.append(
            {
                "month_date": month_date,
                "income": summary["income"],
                "expense": summary["expense"],
                "profit": summary["profit"],
                "unique_clients": client_statistics["unique_clients"],
                "procedures_count": summary["procedures_count"],
                "new_clients": client_statistics["new_clients"],
                "returning_clients": client_statistics["returning_clients"],
            }
        )

    return {
        "total": {
            "income": total_summary["income"],
            "expense": total_summary["expense"],
            "profit": total_summary["profit"],
            "clients": Client.objects.filter(owner=user).count(),
            "procedures": total_summary["procedures_count"],
        },
        "current_month": {
            "income": current_month_summary["income"],
            "expense": current_month_summary["expense"],
            "profit": current_month_summary["profit"],
            "new_clients": current_month_clients["new_clients"],
            "returning_clients": current_month_clients["returning_clients"],
        },
        "monthly": monthly,
    }

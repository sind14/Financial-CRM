from django.urls import path

from finance.views import (
    dashboard_view,
    monthly_expense_delete_view,
    monthly_expense_edit_view,
    monthly_expenses_view,
    payment_delete_view,
    payment_edit_view,
    payments_view,
)

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("payments/", payments_view, name="payments"),
    path("monthly-expenses/", monthly_expenses_view, name="monthly-expenses"),
    path(
        "monthly-expenses/<int:pk>/edit/",
        monthly_expense_edit_view,
        name="monthly-expense-edit",
    ),
    path(
        "monthly-expenses/<int:pk>/delete/",
        monthly_expense_delete_view,
        name="monthly-expense-delete",
    ),
    path("payments/<int:pk>/edit/", payment_edit_view, name="payment-edit"),
    path("payments/<int:pk>/delete/", payment_delete_view, name="payment-delete"),
]

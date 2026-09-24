from django.urls import include, path

from finance.views import (
    statistics_view,
    payments_view,
    payment_add_view,
    payment_edit_view,
    payment_delete_view,
    monthly_expenses_view,
    monthly_expense_detail_view,
    monthly_expense_add_view,
    monthly_expense_edit_view,
    monthly_expense_delete_view,
    clients_view,
    client_detail_view,
    client_add_view,
    client_edit_view,
    client_delete_view,
)

urlpatterns = [
    path("", statistics_view, name="statistics"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("payments/", payments_view, name="payments"),
    path("payments/add/", payment_add_view, name="payment-add"),
    path("payments/<int:pk>/edit/", payment_edit_view, name="payment-edit"),
    path("payments/<int:pk>/delete/", payment_delete_view, name="payment-delete"),

    path("monthly-expenses/", monthly_expenses_view, name="monthly-expenses"),
    path("monthly-expenses/<int:pk>/", monthly_expense_detail_view, name="monthly-expense-detail"),
    path("monthly-expenses/add/", monthly_expense_add_view, name="monthly-expense-add"),
    path("monthly-expenses/<int:pk>/edit/", monthly_expense_edit_view, name="monthly-expense-edit"),
    path("monthly-expenses/<int:pk>/delete/", monthly_expense_delete_view, name="monthly-expense-delete"),

    path("clients/", clients_view, name="clients"),
    path("clients/<int:pk>/", client_detail_view, name="client-detail"),
    path("clients/add/", client_add_view, name="client-add"),
    path("clients/<int:pk>/edit/", client_edit_view, name="client-edit"),
    path("clients/<int:pk>/delete/", client_delete_view, name="client-delete"),
]

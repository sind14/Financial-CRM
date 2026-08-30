from django.contrib import admin

from finance.models import Client, MonthlyExpense, Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("amount", "payment_type", "date", "category")
    list_filter = ("payment_type", "date")
    search_fields = ("category", "description")


@admin.register(MonthlyExpense)
class MonthlyExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "amount",
    )
    search_fields = ("name",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "surname", "phone", "created_at")
    search_fields = ("name", "surname", "phone")

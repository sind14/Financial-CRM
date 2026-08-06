from django.contrib import admin
from finance.models import MonthlyExpense, Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("amount", "payment_type", "date", "category")
    list_filter = ("payment_type", "date")
    search_fields = ("category", "description")


@admin.register(MonthlyExpense)
class MonthlyExpenseAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

from django.contrib import admin

from finance.models import Client, MonthlyExpense, Payment, PaymentService


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("amount", "payment_type", "date", "service", "owner")
    list_filter = ("payment_type", "date", "owner")
    search_fields = ("service", "description")


@admin.register(MonthlyExpense)
class MonthlyExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "amount",
        "owner",
    )
    list_filter = ("owner",)
    search_fields = ("name", "owner__username")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "surname", "phone", "owner", "created_at")
    list_filter = ("owner",)
    search_fields = ("name", "surname", "phone", "owner__username")


@admin.register(PaymentService)
class PaymentServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "default_amount", "owner")
    list_filter = ("owner",)
    search_fields = ("name", "owner__username")

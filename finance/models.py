from django.db import models
from django.conf import settings


class Payment(models.Model):
    class PaymentType(models.TextChoices):
        INCOME = "income"
        EXPENSE = "expense"

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=7, choices=PaymentType.choices)
    date = models.DateField()
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    monthly_expense = models.ForeignKey(
        "MonthlyExpense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.get_payment_type_display()}: {self.amount} — {self.category}"


class MonthlyExpense(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="monthly_expenses",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name} — {self.amount}"

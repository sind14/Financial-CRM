from django.db import models


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


class MonthlyExpense(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
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
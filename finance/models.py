from django.conf import settings
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
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        "Client",
        on_delete=models.SET_NULL,
        related_name="payments",
        null=True,
        blank=True,
    )
    category_option = models.ForeignKey(
        "PaymentCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    def __str__(self):
        return f"{self.get_payment_type_display()}: {self.amount} — {self.category}"


class PaymentCategory(models.Model):
    name = models.CharField(max_length=100)
    default_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_categories",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name} - {self.default_amount}"


class MonthlyExpense(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
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


class Client(models.Model):
    name = models.CharField(max_length=100)
    surname = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="clients",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name} {self.surname}"

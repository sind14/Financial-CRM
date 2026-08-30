from django.core.management.base import BaseCommand
from django.utils import timezone

from finance.models import MonthlyExpense, Payment


class Command(BaseCommand):
    help = "Creates monthly payments from monthly expenses"

    def handle(self, *args, **options):
        first_day_of_month = timezone.localdate().replace(day=1)
        create_count = 0

        monthly_expenses = MonthlyExpense.objects.all()

        for expense in monthly_expenses:
            _, created = Payment.objects.get_or_create(
                monthly_expense=expense,
                date=first_day_of_month,
                defaults={
                    "amount": expense.amount,
                    "payment_type": Payment.PaymentType.EXPENSE,
                    "category": expense.name,
                    "description": "Автоматично створена щомісячна витрата",
                    "owner": expense.owner,
                },
            )

            if created:
                create_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Створено витрату: {expense.name}")
                )

        self.stdout.write(self.style.SUCCESS(f"Створено записів: {create_count}"))

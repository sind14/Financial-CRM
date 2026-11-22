from django.core.management.base import BaseCommand

from finance.models import MonthlyExpense
from finance.services import ensure_monthly_expense_payment


class Command(BaseCommand):
    help = "Creates monthly payments from monthly expenses"

    def handle(self, *args, **options):
        create_count = 0

        monthly_expenses = MonthlyExpense.objects.exclude(owner__isnull=True)

        for expense in monthly_expenses:
            _, created = ensure_monthly_expense_payment(expense)

            if created:
                create_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Створено витрату: {expense.name}")
                )

        self.stdout.write(self.style.SUCCESS(f"Створено записів: {create_count}"))

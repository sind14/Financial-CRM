from datetime import date
from django.core.management.base import BaseCommand
from finance.models import MonthlyExpense, Payment


class Command(BaseCommand):
    help = "Creates monthly payments from active monthly expenses"

    def handle(self, *args, **options):
        first_day_of_month = date.today().replace(day=1)
        create_count = 0

        monthly_expenses = MonthlyExpense.objects.filter(is_active=True)

        for expense in monthly_expenses:
            payment, created = Payment.objects.get_or_create(
                monthly_expense=expense,
                date=first_day_of_month,
                defaults={
                    "amount": expense.amount,
                    "payment_type": Payment.PaymentType.EXPENSE,
                    "category": expense.name,
                    "description": "Автоматично створена щомісячна витрата",
                },
            )

            if created:
                create_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Створено витрату: {expense.name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(f"Створено записів: {create_count}")
        )
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client as TestClient
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from finance.forms import MonthlyExpenseForm, PaymentForm, PaymentServiceForm
from finance.models import Client, MonthlyExpense, Payment, PaymentService

User = get_user_model()


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123",
        )
        self.client = TestClient()
        self.client.login(username="testuser", password="testpassword123")

    def test_payment_service_creation_and_str(self):
        service = PaymentService.objects.create(
            name="Консультація",
            default_amount=Decimal("150.00"),
            owner=self.user,
        )
        self.assertEqual(str(service), "Консультація - 150.00")
        self.assertEqual(self.user.payment_services.count(), 1)
        self.assertEqual(self.user.payment_services.first(), service)

    def test_payment_with_service_str(self):
        service = PaymentService.objects.create(
            name="Масаж",
            default_amount=Decimal("200.00"),
            owner=self.user,
        )
        payment = Payment.objects.create(
            amount=Decimal("200.00"),
            payment_type=Payment.PaymentType.INCOME,
            date=timezone.localdate(),
            service="Масаж",
            service_option=service,
            owner=self.user,
        )
        self.assertIn("Масаж", str(payment))
        self.assertEqual(payment.service_option, service)

    def test_payment_services_list_view(self):
        service = PaymentService.objects.create(
            name="Стрижка",
            default_amount=Decimal("300.00"),
            owner=self.user,
        )
        response = self.client.get(reverse("payment-services"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Стрижка")
        self.assertContains(response, "300.00")
        self.assertContains(response, "service-value")
        self.assertContains(response, f'id="service-delete-btn-{service.pk}"')
        self.assertContains(
            response, reverse("payment-service-delete", kwargs={"pk": service.pk})
        )

    def test_payment_service_add_view(self):
        response = self.client.post(
            reverse("payment-service-add"),
            {"name": "Манікюр", "default_amount": "250.00"},
        )
        self.assertRedirects(response, reverse("payment-services"))
        self.assertTrue(
            PaymentService.objects.filter(
                name="Манікюр",
                owner=self.user,
            ).exists()
        )

    def test_payment_service_edit_view(self):
        service = PaymentService.objects.create(
            name="Педикюр",
            default_amount=Decimal("350.00"),
            owner=self.user,
        )
        response = self.client.post(
            reverse("payment-service-edit", kwargs={"pk": service.pk}),
            {"name": "Педикюр преміум", "default_amount": "400.00"},
        )
        self.assertRedirects(response, reverse("payment-services"))
        service.refresh_from_db()
        self.assertEqual(service.name, "Педикюр преміум")
        self.assertEqual(service.default_amount, Decimal("400.00"))

    def test_payment_service_delete_view(self):
        service = PaymentService.objects.create(
            name="Тимчасова послуга",
            default_amount=Decimal("100.00"),
            owner=self.user,
        )
        response = self.client.post(
            reverse("payment-service-delete", kwargs={"pk": service.pk})
        )
        self.assertRedirects(response, reverse("payment-services"))
        self.assertFalse(PaymentService.objects.filter(pk=service.pk).exists())

    def test_payment_add_view_with_service_option(self):
        service = PaymentService.objects.create(
            name="Діагностика",
            default_amount=Decimal("500.00"),
            owner=self.user,
        )
        response = self.client.post(
            reverse("payment-add"),
            {
                "amount": "500.00",
                "payment_type": Payment.PaymentType.INCOME,
                "date": timezone.localdate().strftime("%Y-%m-%d"),
                "service_option": service.pk,
                "description": "Тестовий платіж",
            },
        )
        self.assertRedirects(response, reverse("payments"))
        payment = Payment.objects.filter(owner=self.user).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.service, "Діагностика")
        self.assertEqual(payment.service_option, service)

    def test_amounts_must_be_positive(self):
        payment_form = PaymentForm(
            data={
                "amount": "0",
                "payment_type": Payment.PaymentType.INCOME,
                "date": timezone.localdate().isoformat(),
            },
            user=self.user,
        )
        monthly_expense_form = MonthlyExpenseForm(
            data={"name": "Оренда", "amount": "-1"}
        )
        service_form = PaymentServiceForm(
            data={"name": "Манікюр", "default_amount": "0"}
        )

        self.assertFalse(payment_form.is_valid())
        self.assertFalse(monthly_expense_form.is_valid())
        self.assertFalse(service_form.is_valid())

    def test_payment_edit_clears_service_when_service_is_removed(self):
        service = PaymentService.objects.create(
            name="Манікюр",
            default_amount=Decimal("500.00"),
            owner=self.user,
        )
        payment = Payment.objects.create(
            amount=Decimal("500.00"),
            payment_type=Payment.PaymentType.INCOME,
            date=timezone.localdate(),
            service="Манікюр",
            service_option=service,
            owner=self.user,
        )

        response = self.client.post(
            reverse("payment-edit", kwargs={"pk": payment.pk}),
            {
                "amount": "500.00",
                "payment_type": Payment.PaymentType.EXPENSE,
                "date": timezone.localdate().isoformat(),
                "description": "Повернення коштів",
            },
        )

        self.assertRedirects(response, reverse("payments"))
        payment.refresh_from_db()
        self.assertEqual(payment.service, "")
        self.assertIsNone(payment.service_option)

    def test_user_cannot_edit_another_users_payment(self):
        other_user = User.objects.create_user(
            username="other-user",
            password="testpassword123",
        )
        payment = Payment.objects.create(
            amount=Decimal("500.00"),
            payment_type=Payment.PaymentType.INCOME,
            date=timezone.localdate(),
            service="Манікюр",
            owner=other_user,
        )

        response = self.client.get(reverse("payment-edit", kwargs={"pk": payment.pk}))

        self.assertEqual(response.status_code, 404)

    def test_monthly_expense_and_generate_command(self):
        import io

        expense = MonthlyExpense.objects.create(
            name="Оренда офісу",
            amount=Decimal("10000.00"),
            owner=self.user,
        )
        out = io.StringIO()
        call_command("generate_monthly_expenses", stdout=out)
        payment = Payment.objects.filter(
            monthly_expense=expense,
            owner=self.user,
        ).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.service, "Оренда офісу")

    def test_monthly_expenses_list_view(self):
        expense = MonthlyExpense.objects.create(
            name="Інтернет",
            amount=Decimal("100.00"),
            owner=self.user,
        )
        response = self.client.get(reverse("monthly-expenses"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Інтернет")
        self.assertContains(response, "-100.00 zł")
        self.assertContains(response, "expense-value")
        self.assertContains(response, "amount expense")
        self.assertContains(response, "col-expense-date")
        self.assertContains(response, f'id="expense-delete-btn-{expense.pk}"')
        self.assertContains(
            response, reverse("monthly-expense-delete", kwargs={"pk": expense.pk})
        )

    def test_monthly_expense_edit_view(self):
        expense = MonthlyExpense.objects.create(
            name="Комуналка",
            amount=Decimal("500.00"),
            owner=self.user,
        )
        response = self.client.post(
            reverse("monthly-expense-edit", kwargs={"pk": expense.pk}),
            {"name": "Комунальні послуги", "amount": "600.00"},
        )
        self.assertRedirects(response, reverse("monthly-expenses"))
        expense.refresh_from_db()
        self.assertEqual(expense.name, "Комунальні послуги")
        self.assertEqual(expense.amount, Decimal("600.00"))

    def test_clients_list_and_add_inline(self):
        Client.objects.create(
            name="Іван",
            surname="Франко",
            phone="+380501234567",
            owner=self.user,
        )
        response = self.client.get(reverse("clients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Іван Франко")
        self.assertContains(response, "+380501234567")
        self.assertContains(response, 'id="btn-add-client"')
        self.assertContains(response, 'id="new-client-row"')
        self.assertContains(response, reverse("client-add"))

        # Test adding a client via POST to client-add
        add_response = self.client.post(
            reverse("client-add"),
            {"name": "Леся", "surname": "Українка", "phone": "+380509876543"},
        )
        self.assertRedirects(add_response, reverse("clients"))
        self.assertTrue(
            Client.objects.filter(
                name="Леся", surname="Українка", owner=self.user
            ).exists()
        )

    def test_add_views_redirect_get_requests(self):
        self.assertRedirects(self.client.get(reverse("client-add")), reverse("clients"))
        self.assertRedirects(
            self.client.get(reverse("payment-service-add")), reverse("payment-services")
        )
        self.assertRedirects(
            self.client.get(reverse("monthly-expense-add")), reverse("monthly-expenses")
        )

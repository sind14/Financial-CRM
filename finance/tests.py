from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client as TestClient, TestCase
from django.urls import reverse
from django.utils import timezone

from finance.forms import PaymentForm, PaymentServiceForm
from finance.models import Client, MonthlyExpense, Payment, PaymentService
from finance.serializers import PaymentSerializer

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

    def test_payment_serializer(self):
        payment = Payment.objects.create(
            amount=Decimal("120.00"),
            payment_type=Payment.PaymentType.INCOME,
            date=timezone.localdate(),
            service="Консультація",
            owner=self.user,
        )
        serializer = PaymentSerializer(payment)
        self.assertEqual(serializer.data["service"], "Консультація")
        self.assertNotIn("category", serializer.data)

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client as WebClient
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from finance.models import Client, MonthlyExpense, Payment, PaymentService
from finance.services import MONTHLY_EXPENSE_DESCRIPTION

User = get_user_model()
PASSWORD = "testpassword123"
COOKIE = settings.JWT_REFRESH_COOKIE_NAME


def api_url(path):
    return f"/api/v1/{path}"


class AuthenticatedAPITestCase(APITestCase):
    def setUp(self):
        cache.clear()  # reset auth throttling between tests
        self.user = User.objects.create_user(username="owner", password=PASSWORD)
        self.other_user = User.objects.create_user(
            username="stranger", password=PASSWORD
        )
        self.client.force_authenticate(self.user)

    def create_payment(self, owner=None, **kwargs):
        data = {
            "amount": Decimal("100.00"),
            "payment_type": Payment.PaymentType.INCOME,
            "date": timezone.localdate(),
            "service": "",
            "owner": owner or self.user,
        }
        data.update(kwargs)
        return Payment.objects.create(**data)


class WebAuthTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="owner", password=PASSWORD)

    def login(self):
        return self.client.post(
            api_url("auth/login/"),
            {"username": "owner", "password": PASSWORD},
            format="json",
        )

    def test_login_returns_access_and_sets_httponly_refresh_cookie(self):
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertEqual(response.data["user"]["username"], "owner")

        cookie = response.cookies[COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], settings.JWT_REFRESH_COOKIE_PATH)
        self.assertEqual(cookie["samesite"], settings.JWT_REFRESH_COOKIE_SAMESITE)

    def test_login_with_wrong_password_is_rejected(self):
        response = self.client.post(
            api_url("auth/login/"),
            {"username": "owner", "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn(COOKIE, response.cookies)

    def test_access_token_authenticates_requests(self):
        access = self.login().data["access"]
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = client.get(api_url("auth/me/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "owner")

    def test_refresh_rotates_cookie_and_blacklists_old_token(self):
        old_refresh = self.login().cookies[COOKIE].value

        response = self.client.post(api_url("auth/refresh/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        new_refresh = response.cookies[COOKIE].value
        self.assertNotEqual(new_refresh, old_refresh)

        self.client.cookies[COOKIE] = old_refresh
        reused = self.client.post(api_url("auth/refresh/"))
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_without_cookie_is_rejected(self):
        response = self.client.post(api_url("auth/refresh/"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_revokes_refresh_token_and_clears_cookie(self):
        refresh = self.login().cookies[COOKIE].value

        response = self.client.post(api_url("auth/logout/"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.cookies[COOKIE].value, "")

        self.client.cookies[COOKIE] = refresh
        after_logout = self.client.post(api_url("auth/refresh/"))
        self.assertEqual(after_logout.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_is_throttled(self):
        for _ in range(10):
            self.client.post(
                api_url("auth/login/"),
                {"username": "owner", "password": "wrong"},
                format="json",
            )

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class MobileAuthTests(APITestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(username="owner", password=PASSWORD)

    def test_token_pair_refresh_and_blacklist(self):
        tokens = self.client.post(
            api_url("auth/token/"),
            {"username": "owner", "password": PASSWORD},
            format="json",
        ).data
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)

        refreshed = self.client.post(
            api_url("auth/token/refresh/"),
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        new_refresh = refreshed.data["refresh"]

        blacklisted = self.client.post(
            api_url("auth/token/blacklist/"),
            {"refresh": new_refresh},
            format="json",
        )
        self.assertEqual(blacklisted.status_code, status.HTTP_200_OK)

        reused = self.client.post(
            api_url("auth/token/refresh/"),
            {"refresh": new_refresh},
            format="json",
        )
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)


class AnonymousAccessTests(APITestCase):
    def test_endpoints_require_authentication(self):
        for path in (
            "payments/",
            "payment-services/",
            "monthly-expenses/",
            "clients/",
            "clients/search/?q=a",
            "statistics/",
            "auth/me/",
            "schema/",
        ):
            with self.subTest(path=path):
                response = self.client.get(api_url(path))
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_bearer_token_is_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
        response = self.client.get(api_url("payments/"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_session_auth_requires_csrf_for_writes(self):
        User.objects.create_user(username="owner", password=PASSWORD)
        client = APIClient(enforce_csrf_checks=True)
        client.login(username="owner", password=PASSWORD)

        self.assertEqual(
            client.get(api_url("payments/")).status_code, status.HTTP_200_OK
        )
        response = client.post(
            api_url("clients/"), {"name": "A", "surname": "B"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PaymentAPITests(AuthenticatedAPITestCase):
    def test_create_sets_owner_and_service_name(self):
        service = PaymentService.objects.create(
            name="Масаж", default_amount=Decimal("200.00"), owner=self.user
        )
        client = Client.objects.create(name="Іра", surname="Коваль", owner=self.user)

        response = self.client.post(
            api_url("payments/"),
            {
                "amount": "200.00",
                "payment_type": "income",
                "date": "2026-11-01",
                "service_option": service.pk,
                "client": client.pk,
                "description": "test",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payment = Payment.objects.get(pk=response.data["id"])
        self.assertEqual(payment.owner, self.user)
        self.assertEqual(payment.service, "Масаж")
        self.assertEqual(response.data["service"], "Масаж")
        self.assertEqual(response.data["client_name"], "Іра Коваль")

    def test_owner_in_payload_is_ignored(self):
        response = self.client.post(
            api_url("payments/"),
            {
                "amount": "10.00",
                "payment_type": "expense",
                "date": "2026-11-01",
                "owner": self.other_user.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Payment.objects.get().owner, self.user)

    def test_update_clears_service_when_option_removed(self):
        service = PaymentService.objects.create(
            name="Масаж", default_amount=Decimal("200.00"), owner=self.user
        )
        payment = self.create_payment(service="Масаж", service_option=service)

        response = self.client.patch(
            api_url(f"payments/{payment.pk}/"),
            {"service_option": None},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payment.refresh_from_db()
        self.assertIsNone(payment.service_option)
        self.assertEqual(payment.service, "")

    def test_amount_must_be_positive(self):
        for amount in ("0", "-5.00"):
            with self.subTest(amount=amount):
                response = self.client.post(
                    api_url("payments/"),
                    {"amount": amount, "payment_type": "income", "date": "2026-11-01"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("amount", response.data)

    def test_expense_cannot_have_client(self):
        client = Client.objects.create(name="A", surname="B", owner=self.user)
        response = self.client.post(
            api_url("payments/"),
            {
                "amount": "10.00",
                "payment_type": "expense",
                "date": "2026-11-01",
                "client": client.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment_type", response.data)

    def test_patch_to_expense_on_payment_with_client_is_rejected(self):
        client = Client.objects.create(name="A", surname="B", owner=self.user)
        payment = self.create_payment(client=client)

        response = self.client.patch(
            api_url(f"payments/{payment.pk}/"),
            {"payment_type": "expense"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_reference_other_users_client_or_service(self):
        foreign_client = Client.objects.create(
            name="A", surname="B", owner=self.other_user
        )
        foreign_service = PaymentService.objects.create(
            name="X", default_amount=Decimal("1.00"), owner=self.other_user
        )

        for field, pk in (
            ("client", foreign_client.pk),
            ("service_option", foreign_service.pk),
        ):
            with self.subTest(field=field):
                response = self.client.post(
                    api_url("payments/"),
                    {
                        "amount": "10.00",
                        "payment_type": "income",
                        "date": "2026-11-01",
                        field: pk,
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

    def test_other_users_payments_are_invisible(self):
        foreign = self.create_payment(owner=self.other_user)
        own = self.create_payment()

        listing = self.client.get(api_url("payments/"))
        self.assertEqual([item["id"] for item in listing.data["results"]], [own.pk])

        url = api_url(f"payments/{foreign.pk}/")
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(url, {"amount": "1.00"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Payment.objects.filter(pk=foreign.pk).exists())

    def test_delete(self):
        payment = self.create_payment()
        response = self.client.delete(api_url(f"payments/{payment.pk}/"))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Payment.objects.filter(pk=payment.pk).exists())

    def test_list_filters(self):
        client = Client.objects.create(name="A", surname="B", owner=self.user)
        early = self.create_payment(date=date(2026, 1, 10), client=client)
        late_expense = self.create_payment(
            date=date(2026, 3, 10), payment_type=Payment.PaymentType.EXPENSE
        )

        def ids(query):
            response = self.client.get(api_url(f"payments/?{query}"))
            self.assertEqual(response.status_code, status.HTTP_200_OK, query)
            return {item["id"] for item in response.data["results"]}

        self.assertEqual(ids("payment_type=expense"), {late_expense.pk})
        self.assertEqual(ids("date_from=2026-02-01"), {late_expense.pk})
        self.assertEqual(ids("date_to=2026-02-01"), {early.pk})
        self.assertEqual(ids(f"client={client.pk}"), {early.pk})

    def test_list_rejects_invalid_filters(self):
        for query in ("payment_type=gift", "date_from=yesterday", "client=abc"):
            with self.subTest(query=query):
                response = self.client.get(api_url(f"payments/?{query}"))
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PaymentServiceAPITests(AuthenticatedAPITestCase):
    def test_crud(self):
        created = self.client.post(
            api_url("payment-services/"),
            {"name": "Манікюр", "default_amount": "250.00"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        service = PaymentService.objects.get(pk=created.data["id"])
        self.assertEqual(service.owner, self.user)

        url = api_url(f"payment-services/{service.pk}/")
        updated = self.client.patch(url, {"default_amount": "300.00"}, format="json")
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        service.refresh_from_db()
        self.assertEqual(service.default_amount, Decimal("300.00"))

        self.assertEqual(
            self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(PaymentService.objects.exists())

    def test_default_amount_must_be_positive(self):
        response = self.client.post(
            api_url("payment-services/"),
            {"name": "X", "default_amount": "0"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_users_services_are_invisible(self):
        foreign = PaymentService.objects.create(
            name="X", default_amount=Decimal("1.00"), owner=self.other_user
        )
        self.assertEqual(self.client.get(api_url("payment-services/")).data["count"], 0)
        self.assertEqual(
            self.client.delete(api_url(f"payment-services/{foreign.pk}/")).status_code,
            status.HTTP_404_NOT_FOUND,
        )


class MonthlyExpenseAPITests(AuthenticatedAPITestCase):
    def test_create_adds_current_month_payment(self):
        response = self.client.post(
            api_url("monthly-expenses/"),
            {"name": "Оренда", "amount": "1500.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        expense = MonthlyExpense.objects.get(pk=response.data["id"])
        self.assertEqual(expense.owner, self.user)

        payment = Payment.objects.get(monthly_expense=expense)
        self.assertEqual(payment.date, timezone.localdate().replace(day=1))
        self.assertEqual(payment.amount, Decimal("1500.00"))
        self.assertEqual(payment.payment_type, Payment.PaymentType.EXPENSE)
        self.assertEqual(payment.owner, self.user)

    def test_update_syncs_only_current_month_payment(self):
        expense = MonthlyExpense.objects.create(
            name="Оренда", amount=Decimal("1500.00"), owner=self.user
        )
        first_day = timezone.localdate().replace(day=1)
        current = self.create_payment(
            monthly_expense=expense,
            date=first_day,
            amount=expense.amount,
            payment_type=Payment.PaymentType.EXPENSE,
        )
        previous = self.create_payment(
            monthly_expense=expense,
            date=(first_day - timedelta(days=1)).replace(day=1),
            amount=expense.amount,
            payment_type=Payment.PaymentType.EXPENSE,
        )

        response = self.client.patch(
            api_url(f"monthly-expenses/{expense.pk}/"),
            {"name": "Нова оренда", "amount": "1800.00"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        current.refresh_from_db()
        previous.refresh_from_db()
        self.assertEqual(current.amount, Decimal("1800.00"))
        self.assertEqual(current.service, "Нова оренда")
        self.assertEqual(previous.amount, Decimal("1500.00"))

    def test_other_users_expenses_are_invisible(self):
        foreign = MonthlyExpense.objects.create(
            name="X", amount=Decimal("1.00"), owner=self.other_user
        )
        self.assertEqual(self.client.get(api_url("monthly-expenses/")).data["count"], 0)
        self.assertEqual(
            self.client.patch(
                api_url(f"monthly-expenses/{foreign.pk}/"),
                {"amount": "2.00"},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )


class ClientAPITests(AuthenticatedAPITestCase):
    def test_create_update_delete(self):
        created = self.client.post(
            api_url("clients/"),
            {"name": "Олена", "surname": "Шевченко", "phone": "+380"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        client = Client.objects.get(pk=created.data["id"])
        self.assertEqual(client.owner, self.user)

        url = api_url(f"clients/{client.pk}/")
        self.assertEqual(
            self.client.patch(url, {"phone": "123"}, format="json").status_code,
            status.HTTP_200_OK,
        )
        client.refresh_from_db()
        self.assertEqual(client.phone, "123")

        payment = self.create_payment(client=client)
        self.assertEqual(
            self.client.delete(url).status_code, status.HTTP_204_NO_CONTENT
        )
        payment.refresh_from_db()
        self.assertIsNone(payment.client)

    def test_list_includes_visit_stats(self):
        client = Client.objects.create(name="A", surname="B", owner=self.user)
        self.create_payment(
            client=client, amount=Decimal("100.00"), date=date(2026, 1, 1)
        )
        self.create_payment(
            client=client, amount=Decimal("50.00"), date=date(2026, 2, 1)
        )

        item = self.client.get(api_url("clients/")).data["results"][0]

        self.assertEqual(item["visits_count"], 2)
        self.assertEqual(item["last_visit"], "2026-02-01")
        self.assertEqual(item["total_spent"], "150.00")

    def test_search(self):
        Client.objects.create(name="Олена", surname="Шевченко", owner=self.user)
        Client.objects.create(name="Олена", surname="Коваль", owner=self.user)
        Client.objects.create(name="Олена", surname="Шевченко", owner=self.other_user)

        response = self.client.get(api_url("clients/search/?q=олена шевч"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["surname"], "Шевченко")

        self.assertEqual(self.client.get(api_url("clients/search/?q=")).data, [])

    def test_client_payments_lists_only_income(self):
        client = Client.objects.create(name="A", surname="B", owner=self.user)
        income = self.create_payment(client=client)
        self.create_payment(payment_type=Payment.PaymentType.EXPENSE)

        response = self.client.get(api_url(f"clients/{client.pk}/payments/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data["results"]], [income.pk])

    def test_other_users_clients_are_invisible(self):
        foreign = Client.objects.create(name="A", surname="B", owner=self.other_user)
        self.assertEqual(self.client.get(api_url("clients/")).data["count"], 0)
        for path in (f"clients/{foreign.pk}/", f"clients/{foreign.pk}/payments/"):
            with self.subTest(path=path):
                self.assertEqual(
                    self.client.get(api_url(path)).status_code,
                    status.HTTP_404_NOT_FOUND,
                )


class StatisticsAPITests(AuthenticatedAPITestCase):
    def test_statistics(self):
        today = timezone.localdate()
        client = Client.objects.create(name="A", surname="B", owner=self.user)
        self.create_payment(client=client, amount=Decimal("300.00"), date=today)
        self.create_payment(
            amount=Decimal("100.00"),
            date=today,
            payment_type=Payment.PaymentType.EXPENSE,
        )
        self.create_payment(owner=self.other_user, amount=Decimal("999.00"))

        response = self.client.get(api_url("statistics/"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["total"],
            {
                "income": "300.00",
                "expense": "100.00",
                "profit": "200.00",
                "clients": 1,
                "procedures": 1,
            },
        )
        self.assertEqual(response.data["current_month"]["profit"], "200.00")
        self.assertEqual(response.data["current_month"]["new_clients"], 1)

        month = response.data["monthly"][0]
        self.assertEqual((month["year"], month["month"]), (today.year, today.month))
        self.assertEqual(month["unique_clients"], 1)


class TokenOwnershipTests(APITestCase):
    def test_token_only_grants_access_to_own_data(self):
        user = User.objects.create_user(username="owner", password=PASSWORD)
        other = User.objects.create_user(username="stranger", password=PASSWORD)
        Client.objects.create(name="Mine", surname="C", owner=user)
        Client.objects.create(name="Theirs", surname="C", owner=other)

        access = str(RefreshToken.for_user(user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        names = [
            c["name"] for c in self.client.get(api_url("clients/")).data["results"]
        ]
        self.assertEqual(names, ["Mine"])


class MonthlyExpenseDescriptionTests(AuthenticatedAPITestCase):
    def test_all_creation_paths_use_the_same_description(self):
        self.client.post(
            api_url("monthly-expenses/"),
            {"name": "Через API", "amount": "10.00"},
            format="json",
        )

        web = WebClient()
        web.force_login(self.user)
        web.post("/monthly-expenses/add/", {"name": "Через сайт", "amount": "20.00"})

        MonthlyExpense.objects.create(
            name="Через команду", amount=Decimal("30.00"), owner=self.user
        )
        call_command("generate_monthly_expenses", stdout=StringIO())

        descriptions = dict(
            Payment.objects.filter(monthly_expense__isnull=False).values_list(
                "service", "description"
            )
        )
        self.assertEqual(
            descriptions,
            {
                "Через API": MONTHLY_EXPENSE_DESCRIPTION,
                "Через сайт": MONTHLY_EXPENSE_DESCRIPTION,
                "Через команду": MONTHLY_EXPENSE_DESCRIPTION,
            },
        )

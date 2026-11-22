from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from finance import services
from finance.api.serializers import (
    ClientSerializer,
    ClientWithStatsSerializer,
    MonthlyExpenseSerializer,
    PaymentSerializer,
    PaymentServiceSerializer,
    StatisticsSerializer,
)
from finance.models import Client, MonthlyExpense, Payment, PaymentService


class OwnedModelViewSet(viewsets.ModelViewSet):
    """CRUD limited to the requesting user's records.

    Records of other users are reported as 404, never 403, so their existence
    is not revealed.
    """

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(
    parameters=[
        OpenApiParameter("payment_type", enum=Payment.PaymentType.values),
        OpenApiParameter("date_from", type=str, description="YYYY-MM-DD, inclusive"),
        OpenApiParameter("date_to", type=str, description="YYYY-MM-DD, inclusive"),
        OpenApiParameter("client", type=int),
    ]
)
class PaymentViewSet(OwnedModelViewSet):
    # Model hint for schema generation; real data comes from get_queryset().
    queryset = Payment.objects.none()
    serializer_class = PaymentSerializer

    def get_queryset(self):
        payments = services.get_user_payments(self.request.user)

        if self.action != "list":
            return payments

        params = self.request.query_params

        payment_type = params.get("payment_type")
        if payment_type:
            if payment_type not in Payment.PaymentType.values:
                raise ValidationError({"payment_type": "Invalid payment type."})
            payments = payments.filter(payment_type=payment_type)

        for param, lookup in (("date_from", "date__gte"), ("date_to", "date__lte")):
            value = params.get(param)
            if value:
                parsed = parse_date(value)
                if parsed is None:
                    raise ValidationError({param: "Use the YYYY-MM-DD format."})
                payments = payments.filter(**{lookup: parsed})

        client = params.get("client")
        if client:
            if not client.isdigit():
                raise ValidationError({"client": "Must be an integer id."})
            payments = payments.filter(client_id=int(client))

        return payments

    def perform_create(self, serializer):
        # The serializer sets the owner and keeps `service` in sync.
        serializer.save()


class PaymentServiceViewSet(OwnedModelViewSet):
    # Model hint for schema generation; real data comes from get_queryset().
    queryset = PaymentService.objects.none()
    serializer_class = PaymentServiceSerializer

    def get_queryset(self):
        return services.get_user_payment_services(self.request.user)


class MonthlyExpenseViewSet(OwnedModelViewSet):
    # Model hint for schema generation; real data comes from get_queryset().
    queryset = MonthlyExpense.objects.none()
    serializer_class = MonthlyExpenseSerializer

    def get_queryset(self):
        return services.get_user_monthly_expenses(self.request.user)

    def perform_create(self, serializer):
        # The serializer sets the owner and creates this month's payment.
        serializer.save()


class ClientViewSet(OwnedModelViewSet):
    # Model hint for schema generation; real data comes from get_queryset().
    queryset = Client.objects.none()

    def get_queryset(self):
        if self.action in ("list", "retrieve"):
            return services.get_user_clients_with_stats(self.request.user)
        return services.get_user_clients(self.request.user)

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return ClientWithStatsSerializer
        if self.action == "payments":
            return PaymentSerializer
        return ClientSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "q",
                type=str,
                required=True,
                description="Words matched against name, surname and phone.",
            )
        ],
        responses=ClientSerializer(many=True),
    )
    @action(detail=False, methods=["get"], pagination_class=None)
    def search(self, request):
        clients = services.search_clients(
            request.user, request.query_params.get("q", "").strip()
        )
        return Response(ClientSerializer(clients, many=True).data)

    @extend_schema(responses=PaymentSerializer(many=True))
    @action(detail=True, methods=["get"])
    def payments(self, request, pk=None):
        client = self.get_object()
        payments = services.get_client_income_payments(
            request.user, client
        ).select_related("client", "service_option")
        page = self.paginate_queryset(payments)
        serializer = PaymentSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)


class StatisticsView(APIView):
    @extend_schema(responses=StatisticsSerializer)
    def get(self, request):
        return Response(
            StatisticsSerializer(services.get_statistics(request.user)).data
        )

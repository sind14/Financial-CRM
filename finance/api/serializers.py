from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from finance import services
from finance.models import Client, MonthlyExpense, Payment, PaymentService

POSITIVE_AMOUNT = {
    "min_value": Decimal("0.01"),
    "error_messages": {"min_value": _("Amount must be greater than zero.")},
}


class OwnedPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    """A FK field that only accepts objects owned by the requesting user."""

    def __init__(self, get_queryset, **kwargs):
        self._get_owned_queryset = get_queryset
        super().__init__(**kwargs)

    def get_queryset(self):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return self._get_owned_queryset(None).none()
        return self._get_owned_queryset(request.user)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "first_name", "last_name", "email")
        read_only_fields = fields


class PaymentServiceSerializer(serializers.ModelSerializer):
    default_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, **POSITIVE_AMOUNT
    )

    class Meta:
        model = PaymentService
        fields = ("id", "name", "default_amount")


class MonthlyExpenseSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, **POSITIVE_AMOUNT
    )

    class Meta:
        model = MonthlyExpense
        fields = ("id", "name", "amount", "created_at")
        read_only_fields = ("created_at",)

    def create(self, validated_data):
        return services.create_monthly_expense(
            MonthlyExpense(**validated_data),
            owner=self.context["request"].user,
        )

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        return services.update_monthly_expense(instance)


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ("id", "name", "surname", "phone", "created_at")
        read_only_fields = ("created_at",)


class ClientWithStatsSerializer(ClientSerializer):
    visits_count = serializers.IntegerField(read_only=True)
    last_visit = serializers.DateField(read_only=True, allow_null=True)
    total_spent = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta(ClientSerializer.Meta):
        fields = (
            *ClientSerializer.Meta.fields,
            "visits_count",
            "last_visit",
            "total_spent",
        )
        read_only_fields = (
            *ClientSerializer.Meta.read_only_fields,
            "visits_count",
            "last_visit",
            "total_spent",
        )


class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, **POSITIVE_AMOUNT
    )
    client = OwnedPrimaryKeyRelatedField(
        services.get_user_clients,
        allow_null=True,
        required=False,
    )
    service_option = OwnedPrimaryKeyRelatedField(
        services.get_user_payment_services,
        allow_null=True,
        required=False,
    )
    client_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id",
            "amount",
            "payment_type",
            "date",
            "service_option",
            "service",
            "description",
            "client",
            "client_name",
            "monthly_expense",
            "created_at",
        )
        read_only_fields = ("service", "monthly_expense", "created_at")

    def get_client_name(self, payment) -> str | None:
        return str(payment.client) if payment.client else None

    def validate(self, attrs):
        client = attrs.get("client", getattr(self.instance, "client", None))
        payment_type = attrs.get(
            "payment_type", getattr(self.instance, "payment_type", None)
        )

        if client is not None and payment_type == Payment.PaymentType.EXPENSE:
            raise serializers.ValidationError(
                {"payment_type": _("Expenses cannot be assigned to a client.")}
            )

        return attrs

    def create(self, validated_data):
        return services.save_payment(
            Payment(owner=self.context["request"].user, **validated_data)
        )

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        return services.save_payment(instance)


class StatisticsTotalSerializer(serializers.Serializer):
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    clients = serializers.IntegerField()
    procedures = serializers.IntegerField()


class StatisticsCurrentMonthSerializer(serializers.Serializer):
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    new_clients = serializers.IntegerField()
    returning_clients = serializers.IntegerField()


class StatisticsMonthSerializer(serializers.Serializer):
    year = serializers.IntegerField(source="month_date.year")
    month = serializers.IntegerField(source="month_date.month")
    income = serializers.DecimalField(max_digits=14, decimal_places=2)
    expense = serializers.DecimalField(max_digits=14, decimal_places=2)
    profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    unique_clients = serializers.IntegerField()
    procedures_count = serializers.IntegerField()
    new_clients = serializers.IntegerField()
    returning_clients = serializers.IntegerField()


class StatisticsSerializer(serializers.Serializer):
    total = StatisticsTotalSerializer()
    current_month = StatisticsCurrentMonthSerializer()
    monthly = StatisticsMonthSerializer(many=True)

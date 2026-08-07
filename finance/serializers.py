from rest_framework import serializers

from finance.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "amount",
            "payment_type",
            "date",
            "category",
            "description",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "owner")
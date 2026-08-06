from rest_framework import generics
from finance.models import Payment
from finance.serializers import PaymentSerializer


class PaymentListCreateView(generics.ListCreateAPIView):
    queryset = Payment.objects.all().order_by("-date", "-created_at")
    serializer_class = PaymentSerializer

from django import forms
from django.utils.translation import gettext_lazy as _

from finance.models import Client, MonthlyExpense, Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = (
            "amount",
            "payment_type",
            "date",
            "category",
            "description",
            "client",
        )
        labels = {
            "amount": _("Amount"),
            "payment_type": _("Payment type"),
            "date": _("Date"),
            "category": _("Category"),
            "description": _("Description"),
            "client": _("Client"),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["client"].queryset = Client.objects.filter(
                owner=user
            ).order_by("surname", "name")


class MonthlyExpenseForm(forms.ModelForm):
    class Meta:
        model = MonthlyExpense
        fields = (
            "name",
            "amount",
        )
        labels = {
            "name": _("Name"),
            "amount": _("Amount"),
        }


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = (
            "name",
            "surname",
            "phone",
        )
        labels = {
            "name": _("Name"),
            "surname": _("Surname"),
            "phone": _("Phone"),
        }

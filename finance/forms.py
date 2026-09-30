from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from finance.models import Client, MonthlyExpense, Payment, PaymentService


def validate_positive_amount(value):
    if value is not None and value <= 0:
        raise ValidationError(_("Amount must be greater than zero."))

    return value


class PaymentServiceSelect(forms.Select):
    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex,
            attrs,
        )

        instance = getattr(value, "instance", None)

        if instance:
            option["attrs"]["data-default-amount"] = str(instance.default_amount)

        return option


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = (
            "amount",
            "payment_type",
            "date",
            "service_option",
            "description",
            "client",
        )
        labels = {
            "amount": _("Amount"),
            "payment_type": _("Payment type"),
            "date": _("Date"),
            "service_option": _("Service"),
            "description": _("Description"),
            "client": _("Client"),
        }
        widgets = {
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "service_option": PaymentServiceSelect(),
            "date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["service_option"].empty_label = _("Select service...")

        if user is not None:
            self.fields["client"].queryset = Client.objects.filter(owner=user).order_by(
                "surname", "name"
            )

            self.fields["service_option"].queryset = PaymentService.objects.filter(
                owner=user
            ).order_by("name")

        if not self.instance.pk:
            self.initial["date"] = timezone.localdate().isoformat()
            self.initial["payment_type"] = Payment.PaymentType.INCOME

    def clean(self):
        cleaned_data = super().clean()

        client = cleaned_data.get("client")
        payment_type = cleaned_data.get("payment_type")

        if client is not None and payment_type == Payment.PaymentType.EXPENSE:
            self.add_error(
                "payment_type",
                _("Expenses cannot be assigned to a client."),
            )

        return cleaned_data

    def clean_amount(self):
        return validate_positive_amount(self.cleaned_data.get("amount"))


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

    def clean_amount(self):
        return validate_positive_amount(self.cleaned_data.get("amount"))


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


class PaymentServiceForm(forms.ModelForm):
    class Meta:
        model = PaymentService
        fields = (
            "name",
            "default_amount",
        )
        labels = {
            "name": _("Name"),
            "default_amount": _("Default amount"),
        }

    def clean_default_amount(self):
        return validate_positive_amount(self.cleaned_data.get("default_amount"))

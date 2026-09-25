from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from finance.models import Client, MonthlyExpense, Payment, PaymentCategory


class PaymentCategorySelect(forms.Select):
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
            option["attrs"]["data-default-amount"] = str(
                instance.default_amount
            )

        return option


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = (
            "amount",
            "payment_type",
            "date",
            "category_option",
            "description",
            "client",
        )
        labels = {
            "amount": _("Amount"),
            "payment_type": _("Payment type"),
            "date": _("Date"),
            "category_option": _("Category"),
            "description": _("Description"),
            "client": _("Client"),
        }
        widgets = {
            "category_option": PaymentCategorySelect(),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["client"].queryset = Client.objects.filter(
                owner=user
            ).order_by("surname", "name")

            self.fields["category_option"].queryset = (
                PaymentCategory.objects.filter(
                    owner=user
                ).order_by("name")
            )

        if not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()


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


class PaymentCategoryForm(forms.ModelForm):
    class Meta:
        model = PaymentCategory
        fields = (
            "name",
            "default_amount",
        )
        labels = {
            "name": _("Name"),
            "default_amount": _("Default amount"),
        }

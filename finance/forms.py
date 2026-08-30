from django import forms

from finance.models import Client, MonthlyExpense, Payment


class PaymentForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user is not None:
            self.fields["client"].queryset = Client.objects.filter(owner=user).order_by(
                "surname", "name"
            )

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


class MonthlyExpenseForm(forms.ModelForm):
    class Meta:
        model = MonthlyExpense
        fields = (
            "name",
            "amount",
        )


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = (
            "name",
            "surname",
            "phone",
        )

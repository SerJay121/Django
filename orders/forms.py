from django import forms
from django.core.validators import RegexValidator

from .models import Order

phone_validator = RegexValidator(r"^\+?[0-9\s\-()]{9,18}$", "Введіть коректний номер телефону.")


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="ПІБ")
    phone = forms.CharField(max_length=20, validators=[phone_validator], label="Телефон")
    email = forms.EmailField(label="Email")
    city = forms.CharField(max_length=100, label="Місто")
    address = forms.CharField(max_length=255, label="Адреса")
    postal_code = forms.CharField(max_length=10, required=False, label="Індекс")
    payment_method = forms.ChoiceField(
        choices=Order.PaymentMethod.choices,
        initial=Order.PaymentMethod.CARD,
        label="Спосіб оплати",
    )

    def shipping_address(self) -> str:
        data = self.cleaned_data
        parts = [data["address"], data["city"], data.get("postal_code", "")]
        return ", ".join(p for p in parts if p)


class UpdateCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=0, max_value=99)
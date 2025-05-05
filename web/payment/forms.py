from django import forms
from .models import Tariff

class TariffChoiceForm(forms.Form):
    tariff = forms.ModelChoiceField(
        queryset=Tariff.objects.filter(is_active=True),
        widget=forms.RadioSelect,
        empty_label=None,
        label='Выберите тариф'
    )
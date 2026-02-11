from django import forms
from django.utils import timezone

from .models import Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ("date", "amount", "description", "receipt", "notes")
        error_messages = {
            "date": {
                "required": "Вкажіть дату.",
                "invalid": "Невірний формат дати.",
            },
            "amount": {
                "required": "Вкажіть суму.",
                "invalid": "Невірний формат суми.",
                "max_digits": "Сума занадто велика.",
            },
            "description": {
                "required": "Опишіть витрату.",
            },
        }
        widgets = {
            "date": forms.DateInput(format="%Y-%m-%d", attrs={
                "class": "form-input",
                "type": "date",
                "max": "",  # set dynamically in __init__
            }),
            "amount": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "0.00",
                "step": "0.01",
                "min": "0.01",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 2,
                "placeholder": "На що витрачено",
            }),
            "receipt": forms.ClearableFileInput(attrs={
                "class": "form-input",
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 3,
                "placeholder": "Додаткова інформація",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields['date'].localize = False
        self.fields['date'].widget.attrs['max'] = today.isoformat()
        if not self.instance.pk:
            self.fields['date'].initial = today

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError("Сума має бути більше нуля.")
        return amount

    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone.localdate():
            raise forms.ValidationError("Дата не може бути в майбутньому.")
        return date

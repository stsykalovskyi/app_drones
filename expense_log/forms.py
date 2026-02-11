from django import forms
from django.utils import timezone

from .models import Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ("date", "amount", "description", "receipt", "notes")
        widgets = {
            "date": forms.DateInput(attrs={
                "class": "form-input",
                "type": "date"
            }),
            "amount": forms.NumberInput(attrs={
                "class": "form-input",
                "placeholder": "0.00",
                "step": "0.01",
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
        if not self.instance.pk:
            self.fields['date'].initial = timezone.localdate()

from django import forms

from .models import Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ("amount", "description", "receipt", "notes")
        widgets = {
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

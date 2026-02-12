from django import forms

from .models import Category, Comment, Page


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name",)
        error_messages = {
            "name": {
                "required": "Вкажіть назву категорії.",
                "unique": "Категорія з такою назвою вже існує.",
            },
        }
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Назва категорії",
            }),
        }


class PageForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ("title", "category", "body")
        error_messages = {
            "title": {
                "required": "Вкажіть заголовок сторінки.",
                "unique": "Сторінка з таким заголовком вже існує.",
            },
            "body": {
                "required": "Заповніть зміст сторінки.",
            },
        }
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Заголовок сторінки",
            }),
            "category": forms.Select(attrs={
                "class": "form-input",
            }),
            "body": forms.Textarea(attrs={
                "class": "form-input",
                "id": "md-editor",
                "rows": 18,
                "placeholder": "Зміст сторінки (Markdown)",
            }),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        error_messages = {
            "body": {
                "required": "Напишіть коментар.",
            },
        }
        widgets = {
            "body": forms.Textarea(attrs={
                "class": "form-input",
                "rows": 3,
                "placeholder": "Ваш коментар або зауваження...",
            }),
        }

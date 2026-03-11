from django import forms
from django.contrib.contenttypes.models import ContentType

from equipment_accounting.models import FPVDroneType, OpticalDroneType
from .models import (
    DroneOrder, StrikeReport,
    CREW_CHOICES, WEAPON_TYPE_CHOICES, WEAPON_NAME_CHOICES,
    AMMO_CHOICES, INITIATION_CHOICES, TARGET_CHOICES, RESULT_CHOICES,
)

_BLANK = [('', '— Оберіть —')]
_SEL = {'class': 'form-input'}


class StrikeReportForm(forms.ModelForm):
    crew = forms.ChoiceField(
        choices=_BLANK + CREW_CHOICES, label="Екіпаж",
        widget=forms.Select(attrs=_SEL),
    )
    weapon_type = forms.ChoiceField(
        choices=_BLANK + WEAPON_TYPE_CHOICES, label="Засіб",
        widget=forms.Select(attrs=_SEL),
    )
    weapon_name = forms.ChoiceField(
        choices=_BLANK + WEAPON_NAME_CHOICES, label="Назва засобу",
        widget=forms.Select(attrs=_SEL),
    )
    ammo_type = forms.ChoiceField(
        choices=_BLANK + AMMO_CHOICES, label="БК",
        widget=forms.Select(attrs=_SEL),
    )
    initiation_type = forms.ChoiceField(
        choices=_BLANK + INITIATION_CHOICES, label="Ініціація",
        widget=forms.Select(attrs=_SEL),
    )
    target_type = forms.ChoiceField(
        choices=_BLANK + TARGET_CHOICES, label="Ціль",
        widget=forms.Select(attrs=_SEL),
    )
    result_type = forms.ChoiceField(
        choices=_BLANK + RESULT_CHOICES, label="Результат",
        widget=forms.Select(attrs=_SEL),
    )

    class Meta:
        model = StrikeReport
        fields = [
            'strike_date', 'crew', 'weapon_type', 'weapon_name',
            'ammo_type', 'initiation_type', 'target_type', 'result_type', 'notes', 'video',
        ]
        widgets = {
            'strike_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-input'}),
            'video': forms.FileInput(attrs={'class': 'form-input', 'accept': 'video/*'}),
        }
        labels = {
            'strike_date': 'Дата',
            'notes': 'Примітки',
        }


class DroneOrderForm(forms.Form):
    drone_type = forms.ChoiceField(choices=[], label="Тип БПЛА")
    quantity = forms.IntegerField(min_value=1, initial=1, label="Кількість")
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False, label="Примітки"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fpv_ct = ContentType.objects.get_for_model(FPVDroneType)
        optical_ct = ContentType.objects.get_for_model(OpticalDroneType)

        choices = [('', '— Оберіть тип —')]
        fpv_types = list(FPVDroneType.objects.select_related('model').all())
        if fpv_types:
            choices.append(('FPV дрони', [
                (f'{fpv_ct.id}:{t.pk}', str(t)) for t in fpv_types
            ]))
        optical_types = list(OpticalDroneType.objects.select_related('model').all())
        if optical_types:
            choices.append(('Оптичні дрони', [
                (f'{optical_ct.id}:{t.pk}', str(t)) for t in optical_types
            ]))
        self.fields['drone_type'].choices = choices

    def save(self, pilot):
        data = self.cleaned_data
        ct_id, obj_id = data['drone_type'].split(':')
        ct = ContentType.objects.get(id=int(ct_id))
        return DroneOrder.objects.create(
            pilot=pilot,
            content_type=ct,
            object_id=int(obj_id),
            quantity=data['quantity'],
            notes=data.get('notes', ''),
        )


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = DroneOrder
        fields = ['status', 'master_notes']
        widgets = {
            'master_notes': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'status': 'Статус',
            'master_notes': 'Примітки майстра',
        }

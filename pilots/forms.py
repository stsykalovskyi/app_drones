from django import forms
from django.contrib.contenttypes.models import ContentType

from equipment_accounting.models import FPVDroneType, OpticalDroneType
from .models import DroneOrder, StrikeReport


class StrikeReportForm(forms.ModelForm):
    class Meta:
        model = StrikeReport
        fields = [
            'strike_date', 'target_description', 'result_description',
            'drone_used', 'location_description', 'photo',
        ]
        widgets = {
            'strike_date': forms.DateInput(attrs={'type': 'date'}),
            'result_description': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'strike_date': 'Дата удару',
            'target_description': 'Опис цілі',
            'result_description': 'Результат',
            'drone_used': 'Дрон (необов\'язково)',
            'location_description': 'Місце (необов\'язково)',
            'photo': 'Фото (необов\'язково)',
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

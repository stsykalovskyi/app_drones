from django import forms
from django.contrib.contenttypes.models import ContentType

from .models import (
    UAVInstance, Component, PowerTemplate, VideoTemplate,
    FPVDroneType, OpticalDroneType,
    BatteryType, SpoolType, OtherComponentType,
    DroneModel, DronePurpose, Frequency,
)

INPUT_CSS = {"class": "form-input"}


def _build_drone_type_choices():
    """Build choices combining FPV and Optical drone types as `content_type_id-object_id`."""
    choices = [("", "---------")]
    fpv_ct = ContentType.objects.get_for_model(FPVDroneType)
    for dt in FPVDroneType.objects.select_related("model", "model__manufacturer"):
        choices.append((f"{fpv_ct.pk}-{dt.pk}", f"[Радіо] {dt}"))
    opt_ct = ContentType.objects.get_for_model(OpticalDroneType)
    for dt in OpticalDroneType.objects.select_related("model", "model__manufacturer"):
        choices.append((f"{opt_ct.pk}-{dt.pk}", f"[Оптика] {dt}"))
    return choices


def _build_component_type_choices():
    """Build choices combining all component types as `content_type_id-object_id`."""
    choices = [("", "---------")]
    for model_class, label in [
        (BatteryType, "Батарея"),
        (SpoolType, "Котушка"),
        (OtherComponentType, "Інше"),
    ]:
        ct = ContentType.objects.get_for_model(model_class)
        for obj in model_class.objects.all():
            choices.append((f"{ct.pk}-{obj.pk}", f"[{label}] {obj}"))
    return choices


class UAVInstanceForm(forms.ModelForm):
    drone_type = forms.ChoiceField(
        label="Тип БПЛА",
        choices=[],
        widget=forms.Select(attrs=INPUT_CSS),
    )
    quantity = forms.IntegerField(
        label="Кількість",
        min_value=1,
        max_value=100,
        initial=1,
        widget=forms.NumberInput(attrs={**INPUT_CSS, "min": "1", "max": "100"}),
    )
    with_kit = forms.BooleanField(
        label="Комплект",
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )

    class Meta:
        model = UAVInstance
        fields = ("status", "notes")
        widgets = {
            "status": forms.Select(attrs=INPUT_CSS),
            "notes": forms.Textarea(attrs={**INPUT_CSS, "rows": 3, "placeholder": "Примітки"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drone_type"].choices = _build_drone_type_choices()
        if self.instance.pk:
            # Editing — hide quantity and kit, show status
            del self.fields["quantity"]
            del self.fields["with_kit"]
            if self.instance.content_type_id:
                self.fields["drone_type"].initial = (
                    f"{self.instance.content_type_id}-{self.instance.object_id}"
                )
        else:
            # Creating — hide status and notes
            del self.fields["status"]
            del self.fields["notes"]

    def clean_drone_type(self):
        value = self.cleaned_data["drone_type"]
        if not value:
            raise forms.ValidationError("Оберіть тип БПЛА.")
        try:
            ct_id, obj_id = value.split("-")
            ct = ContentType.objects.get(pk=int(ct_id))
            ct.get_object_for_this_type(pk=int(obj_id))
        except (ValueError, ContentType.DoesNotExist, Exception):
            raise forms.ValidationError("Невірний тип БПЛА.")
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)
        ct_id, obj_id = self.cleaned_data["drone_type"].split("-")
        instance.content_type_id = int(ct_id)
        instance.object_id = int(obj_id)
        if not instance.pk:
            instance.status = "inspection"
        if commit:
            instance.save()
        return instance


class ComponentForm(forms.ModelForm):
    component_type_select = forms.ChoiceField(
        label="Тип комплектуючої",
        choices=[],
        widget=forms.Select(attrs=INPUT_CSS),
    )

    class Meta:
        model = Component
        fields = ("status", "assigned_to_uav", "notes")
        widgets = {
            "status": forms.Select(attrs=INPUT_CSS),
            "assigned_to_uav": forms.Select(attrs=INPUT_CSS),
            "notes": forms.Textarea(attrs={**INPUT_CSS, "rows": 3, "placeholder": "Примітки"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["component_type_select"].choices = _build_component_type_choices()
        if self.instance.pk and self.instance.content_type_id:
            self.fields["component_type_select"].initial = (
                f"{self.instance.content_type_id}-{self.instance.object_id}"
            )

    def clean_component_type_select(self):
        value = self.cleaned_data["component_type_select"]
        if not value:
            raise forms.ValidationError("Оберіть тип комплектуючої.")
        try:
            ct_id, obj_id = value.split("-")
            ct = ContentType.objects.get(pk=int(ct_id))
            ct.get_object_for_this_type(pk=int(obj_id))
        except (ValueError, ContentType.DoesNotExist, Exception):
            raise forms.ValidationError("Невірний тип комплектуючої.")
        return value

    def save(self, commit=True):
        instance = super().save(commit=False)
        ct_id, obj_id = self.cleaned_data["component_type_select"].split("-")
        instance.content_type_id = int(ct_id)
        instance.object_id = int(obj_id)
        if commit:
            instance.save()
        return instance


class FPVDroneTypeForm(forms.ModelForm):
    class Meta:
        model = FPVDroneType
        fields = (
            "model", "purpose", "prop_size", "control_frequencies",
            "video_frequency", "power_template", "has_thermal", "notes",
        )
        widgets = {
            "model": forms.Select(attrs=INPUT_CSS),
            "purpose": forms.Select(attrs=INPUT_CSS),
            "prop_size": forms.Select(attrs=INPUT_CSS),
            "control_frequencies": forms.CheckboxSelectMultiple(),
            "video_frequency": forms.Select(attrs=INPUT_CSS),
            "power_template": forms.Select(attrs=INPUT_CSS),
            "has_thermal": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={**INPUT_CSS, "rows": 3, "placeholder": "Примітки"}),
        }


class OpticalDroneTypeForm(forms.ModelForm):
    class Meta:
        model = OpticalDroneType
        fields = (
            "model", "purpose", "prop_size", "control_frequencies",
            "video_template", "power_template", "has_thermal", "notes",
        )
        widgets = {
            "model": forms.Select(attrs=INPUT_CSS),
            "purpose": forms.Select(attrs=INPUT_CSS),
            "prop_size": forms.Select(attrs=INPUT_CSS),
            "control_frequencies": forms.CheckboxSelectMultiple(),
            "video_template": forms.Select(attrs=INPUT_CSS),
            "power_template": forms.Select(attrs=INPUT_CSS),
            "has_thermal": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={**INPUT_CSS, "rows": 3, "placeholder": "Примітки"}),
        }


class PowerTemplateForm(forms.ModelForm):
    class Meta:
        model = PowerTemplate
        fields = ("name", "connector", "configuration", "capacity")
        widgets = {
            "name": forms.TextInput(attrs={**INPUT_CSS, "placeholder": "Назва шаблону"}),
            "connector": forms.Select(attrs=INPUT_CSS),
            "configuration": forms.Select(attrs=INPUT_CSS),
            "capacity": forms.NumberInput(attrs={**INPUT_CSS, "placeholder": "mAh", "min": "1"}),
        }


class VideoTemplateForm(forms.ModelForm):
    class Meta:
        model = VideoTemplate
        fields = ("name", "is_analog", "max_distance")
        widgets = {
            "name": forms.TextInput(attrs={**INPUT_CSS, "placeholder": "Назва шаблону"}),
            "is_analog": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "max_distance": forms.NumberInput(attrs={**INPUT_CSS, "placeholder": "км", "min": "1"}),
        }

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.db.models.expressions import RawSQL

from .models import (
    UAVInstance, Component, PowerTemplate, VideoTemplate,
    FPVDroneType, OpticalDroneType,
    OtherComponentType,
    DroneModel, DronePurpose, Frequency, Manufacturer,
)

INPUT_CSS = {"class": "form-input"}


def _get_available_uavs_for_kind(kind, exclude_component_pk=None):
    """Return active UAVs filtered by component kind.

    Returns empty queryset when kind is unknown.
    For battery/spool excludes UAVs that already have one assigned,
    optionally ignoring a specific component (used on edit).
    For other returns all active UAVs.
    """
    if not kind:
        return UAVInstance.objects.none()

    base_qs = UAVInstance.objects.filter(status__in=UAVInstance.ACTIVE_STATUSES)

    if kind in ('battery', 'spool'):
        occ_qs = Component.objects.filter(kind=kind, assigned_to_uav__isnull=False)
        if exclude_component_pk:
            occ_qs = occ_qs.exclude(pk=exclude_component_pk)
        return base_qs.exclude(pk__in=occ_qs.values_list('assigned_to_uav_id', flat=True))

    return base_qs


def _frequencies_qs():
    """Return frequencies ordered by value normalized to MHz (GHz × 1000)."""
    return Frequency.objects.annotate(
        value_mhz=RawSQL(
            "CASE WHEN unit = 'ghz' THEN value * 1000.0 ELSE value END", []
        )
    ).order_by('value_mhz')


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
        label="Додати комплект",
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
            del self.fields["quantity"]
            del self.fields["with_kit"]
            if self.instance.content_type_id:
                self.fields["drone_type"].initial = (
                    f"{self.instance.content_type_id}-{self.instance.object_id}"
                )
        else:
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
    class Meta:
        model = Component
        fields = ("kind", "power_template", "video_template", "other_type",
                  "status", "assigned_to_uav", "notes")
        widgets = {
            "kind": forms.Select(attrs=INPUT_CSS),
            "power_template": forms.Select(attrs=INPUT_CSS),
            "video_template": forms.Select(attrs=INPUT_CSS),
            "other_type": forms.Select(attrs=INPUT_CSS),
            "status": forms.Select(attrs=INPUT_CSS),
            "assigned_to_uav": forms.Select(attrs=INPUT_CSS),
            "notes": forms.Textarea(attrs={**INPUT_CSS, "rows": 3, "placeholder": "Примітки"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["power_template"].queryset = PowerTemplate.objects.filter(is_deleted=False)
        self.fields["power_template"].required = False
        self.fields["video_template"].queryset = VideoTemplate.objects.filter(is_deleted=False)
        self.fields["video_template"].required = False
        self.fields["other_type"].required = False

        kind = self.instance.kind if self.instance.pk else self.data.get("kind", "")
        self.fields["assigned_to_uav"].queryset = _get_available_uavs_for_kind(
            kind, exclude_component_pk=self.instance.pk or None
        )

    def clean(self):
        cleaned_data = super().clean()
        kind = cleaned_data.get("kind")
        if kind == "battery" and not cleaned_data.get("power_template"):
            self.add_error("power_template", "Оберіть шаблон живлення.")
        if kind == "spool" and not cleaned_data.get("video_template"):
            self.add_error("video_template", "Оберіть шаблон відео.")
        if kind == "other" and not cleaned_data.get("other_type"):
            self.add_error("other_type", "Оберіть тип.")
        return cleaned_data


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['control_frequencies'].queryset = _frequencies_qs()
        self.fields['power_template'].queryset = PowerTemplate.objects.filter(is_deleted=False)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['control_frequencies'].queryset = _frequencies_qs()
        self.fields['power_template'].queryset = PowerTemplate.objects.filter(is_deleted=False)
        self.fields['video_template'].queryset = VideoTemplate.objects.filter(is_deleted=False)


class ManufacturerForm(forms.ModelForm):
    class Meta:
        model = Manufacturer
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(attrs={**INPUT_CSS, "placeholder": "Назва виробника"}),
        }


class DroneModelForm(forms.ModelForm):
    class Meta:
        model = DroneModel
        fields = ("name", "manufacturer")
        widgets = {
            "name": forms.TextInput(attrs={**INPUT_CSS, "placeholder": "Назва моделі"}),
            "manufacturer": forms.Select(attrs=INPUT_CSS),
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
        fields = ("name", "drone_model", "is_analog", "max_distance")
        widgets = {
            "name": forms.TextInput(attrs={**INPUT_CSS, "placeholder": "Назва шаблону"}),
            "drone_model": forms.Select(attrs=INPUT_CSS),
            "is_analog": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "max_distance": forms.NumberInput(attrs={**INPUT_CSS, "placeholder": "км", "min": "1"}),
        }

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.db.models.expressions import RawSQL

from .models import (
    UAVInstance, Component, PowerTemplate, VideoTemplate,
    FPVDroneType, OpticalDroneType,
    OtherComponentType, Location,
    DroneModel, DronePurpose, DroneRole, Frequency, Manufacturer,
)

INPUT_CSS = {"class": "form-input"}


def _get_available_uavs_for_kind(kind, exclude_component_pk=None,
                                  power_template_id=None, video_template_id=None):
    """Return active UAVs filtered by component kind and template compatibility.

    Returns empty queryset when kind is unknown.
    For battery/spool excludes UAVs that already have one assigned.
    When a template id is provided, further filters to UAVs whose drone type
    uses a matching template.
    """
    if not kind:
        return UAVInstance.objects.none()

    base_qs = UAVInstance.objects.filter(status__in=UAVInstance.ACTIVE_STATUSES)

    if kind in ('battery', 'spool'):
        occ_qs = Component.objects.filter(kind=kind, assigned_to_uav__isnull=False)
        if exclude_component_pk:
            occ_qs = occ_qs.exclude(pk=exclude_component_pk)
        base_qs = base_qs.exclude(pk__in=occ_qs.values_list('assigned_to_uav_id', flat=True))

    if kind == 'battery' and power_template_id:
        fpv_ct = ContentType.objects.get_for_model(FPVDroneType)
        opt_ct = ContentType.objects.get_for_model(OpticalDroneType)
        fpv_pks = FPVDroneType.objects.filter(
            power_template_id=power_template_id).values_list('pk', flat=True)
        opt_pks = OpticalDroneType.objects.filter(
            power_template_id=power_template_id).values_list('pk', flat=True)
        base_qs = base_qs.filter(
            Q(content_type=fpv_ct, object_id__in=fpv_pks) |
            Q(content_type=opt_ct, object_id__in=opt_pks)
        )

    if kind == 'spool' and video_template_id:
        try:
            vt = VideoTemplate.objects.get(pk=video_template_id)
            opt_ct = ContentType.objects.get_for_model(OpticalDroneType)
            opt_pks = OpticalDroneType.objects.filter(
                video_template__drone_model_id=vt.drone_model_id,
                video_template__is_analog=vt.is_analog,
            ).values_list('pk', flat=True)
            base_qs = base_qs.filter(content_type=opt_ct, object_id__in=opt_pks)
        except VideoTemplate.DoesNotExist:
            pass

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
    from_location = forms.ModelChoiceField(
        label="Звідки надходять",
        queryset=Location.objects.exclude(location_type='workshop'),
        required=False,
        empty_label="— Оберіть локацію —",
        widget=forms.Select(attrs=INPUT_CSS),
    )
    with_battery = forms.BooleanField(
        label="Додати батарею",
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox", "id": "id_with_battery"}),
    )
    with_spool = forms.BooleanField(
        label="Додати котушку",
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox", "id": "id_with_spool"}),
    )

    class Meta:
        model = UAVInstance
        fields = ("status", "role", "notes")
        widgets = {
            "status": forms.Select(attrs=INPUT_CSS),
            "role": forms.Select(attrs=INPUT_CSS),
            "notes": forms.Textarea(attrs={**INPUT_CSS, "rows": 3, "placeholder": "Примітки"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drone_type"].choices = _build_drone_type_choices()
        self.fields["role"].queryset = DroneRole.objects.all()
        self.fields["role"].label = "Призначення"
        self.fields["role"].empty_label = "— Без призначення —"
        self.fields["role"].required = False
        if self.instance.pk:
            del self.fields["quantity"]
            del self.fields["from_location"]
            del self.fields["with_battery"]
            del self.fields["with_spool"]
            self.fields["status"].choices = [
                c for c in UAVInstance.STATUS_CHOICES if c[0] not in ('deleted', 'given')
            ]
            if self.instance.content_type_id:
                self.fields["drone_type"].initial = (
                    f"{self.instance.content_type_id}-{self.instance.object_id}"
                )
        else:
            del self.fields["status"]
            del self.fields["notes"]
            # Default from_location to "Виробник"
            try:
                self.fields["from_location"].initial = Location.objects.get(
                    location_type='manufacturer'
                ).pk
            except Location.DoesNotExist:
                pass
        # Default призначення to "Ударні" when none is set
        if not self.instance.role_id:
            try:
                default_pk = DroneRole.objects.values_list('pk', flat=True).get(name='Ударні')
                self.initial['role'] = default_pk
            except DroneRole.DoesNotExist:
                pass

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
                  "assigned_to_uav", "notes")
        widgets = {
            "kind": forms.Select(attrs=INPUT_CSS),
            "power_template": forms.Select(attrs=INPUT_CSS),
            "video_template": forms.Select(attrs=INPUT_CSS),
            "other_type": forms.Select(attrs=INPUT_CSS),
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

        if self.instance.pk:
            kind = self.instance.kind
            power_template_id = self.instance.power_template_id
            video_template_id = self.instance.video_template_id
        else:
            kind = self.data.get("kind", "")
            power_template_id = self.data.get("power_template") or None
            video_template_id = self.data.get("video_template") or None
        self.fields["assigned_to_uav"].queryset = _get_available_uavs_for_kind(
            kind,
            exclude_component_pk=self.instance.pk or None,
            power_template_id=power_template_id,
            video_template_id=video_template_id,
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

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.assigned_to_uav:
            instance.status = 'in_use'
        elif instance.status != 'damaged':
            instance.status = 'disassembled'
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
        fields = ("configuration", "capacity", "connector")
        widgets = {
            "configuration": forms.Select(attrs=INPUT_CSS),
            "capacity": forms.NumberInput(attrs={**INPUT_CSS, "placeholder": "mAh", "min": "1"}),
            "connector": forms.Select(attrs=INPUT_CSS),
        }

    def _build_name(self, configuration, capacity, connector):
        conf = configuration.upper().replace('s', 'S').replace('p', 'P')
        conn = connector.upper()
        return f"{conf} {capacity}mAh {conn}"

    def clean(self):
        cleaned_data = super().clean()
        configuration = cleaned_data.get("configuration")
        capacity = cleaned_data.get("capacity")
        connector = cleaned_data.get("connector")
        if configuration and capacity and connector:
            name = self._build_name(configuration, capacity, connector)
            qs = PowerTemplate.objects.filter(name=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Шаблон живлення з такими параметрами вже існує.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.name = self._build_name(
            instance.configuration, instance.capacity, instance.connector
        )
        if commit:
            instance.save()
        return instance


class VideoTemplateForm(forms.ModelForm):
    class Meta:
        model = VideoTemplate
        fields = ("drone_model", "is_analog", "max_distance")
        widgets = {
            "drone_model": forms.Select(attrs=INPUT_CSS),
            "is_analog": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "max_distance": forms.NumberInput(attrs={**INPUT_CSS, "placeholder": "км", "min": "1"}),
        }

    def _build_name(self, drone_model, is_analog, max_distance):
        signal = "аналог" if is_analog else "цифра"
        return f"{drone_model} {signal} {max_distance}км"

    def clean(self):
        cleaned_data = super().clean()
        drone_model = cleaned_data.get("drone_model")
        is_analog = cleaned_data.get("is_analog", False)
        max_distance = cleaned_data.get("max_distance")
        if drone_model and max_distance is not None:
            name = self._build_name(drone_model, is_analog, max_distance)
            qs = VideoTemplate.objects.filter(name=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Шаблон відео з такими параметрами вже існує.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.name = self._build_name(
            instance.drone_model, instance.is_analog, instance.max_distance
        )
        if commit:
            instance.save()
        return instance

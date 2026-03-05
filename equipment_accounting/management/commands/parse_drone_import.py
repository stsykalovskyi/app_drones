"""
Parse a drone-type import text file and resolve every field against the DB.

For each line it outputs all data required to create a full
FPVDroneType or OpticalDroneType record:

  # | Клас | Модель(pk) | Призначення | Пропи | Ctrl | Відео | T | Примітки | К-сть | Статус

Unresolved FK references are shown as  ?<name>  and logged as WARN.

Usage:
  python manage.py parse_drone_import
  python manage.py parse_drone_import temp/my_file.txt
  python manage.py parse_drone_import --errors-only
"""

import os
import re

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from django.contrib.auth.models import User

from equipment_accounting.models import (
    Manufacturer, DroneModel, DronePurpose, Frequency, VideoTemplate, PowerTemplate,
    FPVDroneType, OpticalDroneType, UAVInstance, Component, Location, DroneRole,
)

DEFAULT_FILE = "temp/drone_types_verify.txt"

# Sections whose drones are created with status='deferred'
DEFERRED_SECTIONS = {"НЕ МОЖЕМО ВИКОРИСТОВУВАТИ", "НЕ МОЖЕМО"}


# ── helpers ────────────────────────────────────────────────────────────────

def _load_db():
    """Pre-load all lookup tables into memory."""
    drone_models = {m.name.lower(): m for m in DroneModel.objects.select_related("manufacturer")}
    purposes = {p.pk: p for p in DronePurpose.objects.all()}

    freq_map = {}
    for f in Frequency.objects.all():
        # string key: "900mhz", "2.2ghz"
        freq_map[str(f).lower().replace(" ", "")] = f
        # float key: (900.0, 'mhz') — handles "7GHz" == "7.0GHz"
        freq_map[(float(f.value), f.unit)] = f

    # VideoTemplate: multiple keys per entry
    vt_map = {}
    for vt in VideoTemplate.objects.select_related("drone_model"):
        # full __str__: "Stalker (аналог 20км)"
        vt_map[str(vt).lower()] = vt
        # simplified: "stalker 20км"
        m = re.match(r"^(.+?)\s+\((аналог|цифра)\s+(\d+)км\)$", str(vt), re.IGNORECASE)
        if m:
            short_key = f"{m.group(1).lower()} {m.group(3)}км"
            vt_map[short_key] = vt

    return drone_models, purposes, freq_map, vt_map


def _parse_section_header(header: str) -> dict:
    """
    Extract drone kind, purpose_id, has_thermal from a section header string.
    E.g. 'ДЕНЬ (FPV, purpose=1, has_thermal=false)'
    """
    h = header.strip()
    is_optical = "opticaldronetype" in h.lower() or "ОПТИКА" in h
    kind = "optical" if is_optical else "fpv"

    m = re.search(r"purpose=(\d+)", h)
    purpose_id = int(m.group(1)) if m else 1

    has_thermal = "has_thermal=true" in h.lower()

    deferred = any(kw in h.upper() for kw in DEFERRED_SECTIONS)

    return {
        "kind": kind,
        "purpose_id": purpose_id,
        "has_thermal": has_thermal,
        "deferred": deferred,
        "label": h,
    }


def _normalise_freq(raw: str) -> str:
    return raw.strip().lower().replace(" ", "")


def _parse_freq_value(raw: str):
    """Return (float_value, unit_str) or None."""
    m = re.match(r"^([\d.]+)\s*(mhz|ghz)$", raw.strip(), re.IGNORECASE)
    if not m:
        return None
    return float(m.group(1)), m.group(2).lower()


def _lookup_freq(raw: str, freq_map: dict):
    """Resolve a single frequency string, tolerating float representation."""
    key = _normalise_freq(raw)
    if key in freq_map:
        return freq_map[key]
    parsed = _parse_freq_value(raw)
    if parsed:
        return freq_map.get(parsed)
    return None


def _resolve_freqs(raw: str, freq_map: dict) -> tuple[list, list]:
    """Return (resolved_list, unresolved_list) for a dash-separated freq string."""
    if not raw.strip():
        return [], []
    resolved, unresolved = [], []
    for part in raw.split("-"):
        if not part.strip():
            continue
        f = _lookup_freq(part, freq_map)
        if f:
            resolved.append(f)
        else:
            unresolved.append(part.strip())
    return resolved, unresolved


def _resolve_video_template(raw: str, vt_map: dict):
    key = raw.strip().lower()
    # exact match
    if key in vt_map:
        return vt_map[key], None
    # partial match
    for k, vt in vt_map.items():
        if key in k or k in key:
            return vt, None
    return None, raw.strip()


def _parse_file(path: str, db) -> list[dict]:
    drone_models, purposes, freq_map, vt_map = db
    rows = []
    section = {"kind": "fpv", "purpose_id": 1, "has_thermal": False, "deferred": False, "label": ""}

    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.split("#")[0].rstrip()  # strip inline comment
            line = line.strip()

            if not line:
                continue
            if line.startswith("==="):
                header = line.strip("= ").strip()
                section = _parse_section_header(header)
                continue
            if line.startswith("-") or line.startswith("виробник_"):
                continue

            parts = line.split("_")
            if len(parts) < 2:
                continue
            while len(parts) < 7:
                parts.append("")

            manufacturer_name = parts[0].strip()
            model_name        = parts[1].strip()
            prop_size         = parts[2].strip().rstrip('"')
            ctrl_raw          = parts[3].strip()
            video_raw         = parts[4].strip()
            notes_raw         = parts[5].strip()
            qty_raw           = parts[6].strip()

            if not manufacturer_name:
                continue

            errors = []

            # ── resolve DroneModel ─────────────────────────────────────
            drone_model = drone_models.get(model_name.lower())
            if drone_model is None:
                errors.append(f"DroneModel '{model_name}' not found")

            # ── resolve DronePurpose ───────────────────────────────────
            purpose = purposes.get(section["purpose_id"])
            if purpose is None:
                errors.append(f"DronePurpose pk={section['purpose_id']} not found")

            # ── resolve Frequencies (control) ─────────────────────────
            ctrl_resolved, ctrl_missing = _resolve_freqs(ctrl_raw, freq_map)
            for m in ctrl_missing:
                errors.append(f"Frequency '{m}' not found")

            # ── resolve video ──────────────────────────────────────────
            video_obj = None
            video_missing = None
            if section["kind"] == "fpv":
                if video_raw:
                    video_obj = _lookup_freq(video_raw, freq_map)
                    if video_obj is None:
                        video_missing = video_raw
                        errors.append(f"Frequency(video) '{video_raw}' not found")
            else:  # optical
                if video_raw:
                    video_obj, video_missing = _resolve_video_template(video_raw, vt_map)
                    if video_obj is None:
                        errors.append(f"VideoTemplate '{video_raw}' not found")

            # ── has_thermal ─────────────────────────────────────────────
            has_thermal = section["has_thermal"]
            if "термал" in notes_raw.lower():
                has_thermal = True
                notes_raw = re.sub(r'\bтермал\b', '', notes_raw, flags=re.IGNORECASE).strip()

            # ── quantity ────────────────────────────────────────────────
            qty = None
            if qty_raw and qty_raw != "-":
                try:
                    qty = int(qty_raw)
                except ValueError:
                    pass
            if qty is None:
                m = re.search(r"(\d+)\s*шт", notes_raw, re.IGNORECASE)
                if m:
                    qty = int(m.group(1))

            rows.append({
                "kind":          section["kind"],
                "deferred":      section["deferred"],
                "manufacturer":  manufacturer_name,
                "model_name":    model_name,
                "drone_model":   drone_model,
                "purpose":       purpose,
                "prop_size":     prop_size,
                "ctrl_freqs":    ctrl_resolved,
                "ctrl_raw":      ctrl_raw,
                "video_obj":     video_obj,
                "video_raw":     video_raw,
                "has_thermal":   has_thermal,
                "notes":         notes_raw,
                "qty":           qty,
                "errors":        errors,
            })

    return rows


# ── formatting helpers ──────────────────────────────────────────────────────

def _fmt_model(r: dict) -> str:
    name = r["model_name"] if r["drone_model"] else f"?{r['model_name']}"
    prop = f'{r["prop_size"]}"' if r["prop_size"] else ""

    freq_parts = []
    for f in r["ctrl_freqs"]:
        freq_parts.append(str(f))
    if r["video_obj"]:
        freq_parts.append(str(r["video_obj"]))

    freq_str = " ".join(freq_parts)
    suffix = f" ({prop})" if prop else ""
    suffix += f" ({freq_str})" if freq_str else ""
    return f"{name}{suffix}"


def _fmt_purpose(r: dict) -> str:
    if r["purpose"]:
        return f"{r['purpose'].name} (pk={r['purpose'].pk})"
    return f"?pk={r['purpose']}"


def _fmt_ctrl(r: dict) -> str:
    if not r["ctrl_raw"]:
        return "—"
    parts = []
    for f in r["ctrl_freqs"]:
        parts.append(str(f))
    # add unresolved
    resolved_strs = {_normalise_freq(str(f)) for f in r["ctrl_freqs"]}
    for raw_part in r["ctrl_raw"].split("-"):
        if _normalise_freq(raw_part) not in resolved_strs and raw_part.strip():
            parts.append(f"?{raw_part.strip()}")
    return ", ".join(parts) if parts else "—"


def _fmt_video(r: dict) -> str:
    if r["video_obj"]:
        return f"{r['video_obj']} (pk={r['video_obj'].pk})"
    if r["video_raw"]:
        return f"?{r['video_raw']}"
    return "—"


def _fmt_thermal(r: dict) -> str:
    return "●" if r["has_thermal"] else "○"


def _fmt_status(r: dict) -> str:
    if r["deferred"]:
        return "ВІДКЛ"
    return "ERR" if r["errors"] else "OK"


# ── command ─────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Parse drone import file and resolve all FK fields against the DB"

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            nargs="?",
            default=DEFAULT_FILE,
            help=f"Path to import file (default: {DEFAULT_FILE})",
        )
        parser.add_argument(
            "--errors-only",
            action="store_true",
            help="Show only rows with unresolved references",
        )
        parser.add_argument(
            "--with-qty",
            action="store_true",
            help="Show only rows that have a quantity set",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Create UAVInstance records (default: dry-run preview only)",
        )

    def handle(self, *args, **options):
        path = options["file"]
        if not os.path.isabs(path):
            path = os.path.join(settings.BASE_DIR, path)
        if not os.path.exists(path):
            raise CommandError(f"File not found: {path}")

        db = _load_db()
        rows = _parse_file(path, db)

        if options["errors_only"]:
            rows = [r for r in rows if r["errors"] and not r["deferred"]]

        if options["with_qty"]:
            rows = [r for r in rows if r["qty"] is not None]

        if not rows:
            self.stdout.write(self.style.SUCCESS("No rows to display."))
            return

        self._print_table(rows)
        ok       = sum(1 for r in rows if not r["errors"] and not r["deferred"])
        err      = sum(1 for r in rows if r["errors"])
        deferred = sum(1 for r in rows if r["deferred"])
        self.stdout.write(
            f"\nВсього: {len(rows)}  |  OK: {ok}  |  ERR: {err}  |  ВІДКЛ: {deferred}"
        )

        importable = [r for r in rows if r["qty"] is not None and not r["errors"]]
        if importable:
            self.stdout.write("")
            self._do_import(importable, commit=options["commit"])

    def _print_table(self, rows: list[dict]) -> None:
        headers = ["#", "Клас", "Модель", "Призначення", "T", "Примітки", "К-сть", "Статус"]
        col_w = [len(h) for h in headers]

        data = []
        for i, r in enumerate(rows, 1):
            row = [
                str(i),
                "FPV" if r["kind"] == "fpv" else "Opt",
                _fmt_model(r),
                _fmt_purpose(r),
                _fmt_thermal(r),
                r["notes"] or "—",
                str(r["qty"]) if r["qty"] is not None else "—",
                _fmt_status(r),
            ]
            data.append(row)
            for j, val in enumerate(row):
                col_w[j] = max(col_w[j], len(val))

        sep = "-+-".join("-" * w for w in col_w)
        fmt = " | ".join(f"{{:<{w}}}" for w in col_w)

        self.stdout.write(self.style.SUCCESS(fmt.format(*headers)))
        self.stdout.write(sep)

        prev_kind = None
        for row, r in zip(data, rows):
            if r["kind"] != prev_kind:
                if prev_kind is not None:
                    self.stdout.write(sep)
                prev_kind = r["kind"]

            line = fmt.format(*row)
            if r["errors"]:
                self.stdout.write(self.style.ERROR(line))
            else:
                self.stdout.write(line)

            if r["errors"]:
                for e in r["errors"]:
                    self.stdout.write(self.style.WARNING(f"   ↳ {e}"))

    # ── import ──────────────────────────────────────────────────────────────

    def _find_drone_type(self, r: dict):
        """Return the matching FPVDroneType or OpticalDroneType, or None.

        First tries an exact match (including purpose). If nothing found,
        retries without purpose — useful when the file's section differs from
        the DB purpose. If the purpose-less search returns exactly one result,
        it is used; if multiple, None is returned to avoid false positives.
        """
        base_filters = dict(
            model=r["drone_model"],
            prop_size=r["prop_size"],
            has_thermal=r["has_thermal"],
        )

        def _search_fpv(filters):
            if r["video_obj"]:
                filters["video_frequency"] = r["video_obj"]
            expected_ctrl = {f.pk for f in r["ctrl_freqs"]}
            candidates = list(
                FPVDroneType.objects.filter(**filters).prefetch_related("control_frequencies")
            )
            for c in candidates:
                actual = set(c.control_frequencies.values_list("pk", flat=True))
                if actual == expected_ctrl:
                    return c
            return None

        def _search_opt(filters):
            if r["video_obj"]:
                filters["video_template"] = r["video_obj"]
            return OpticalDroneType.objects.filter(**filters).first()

        if r["kind"] == "fpv":
            result = _search_fpv({**base_filters, "purpose": r["purpose"]} if r["purpose"] else base_filters)
            if result is None and r["purpose"]:
                result = _search_fpv(base_filters)
            return result
        else:
            result = _search_opt({**base_filters, "purpose": r["purpose"]} if r["purpose"] else base_filters)
            if result is None and r["purpose"]:
                result = _search_opt(base_filters)
            return result

    def _create_drone_type(self, r: dict):
        """Create FPVDroneType or OpticalDroneType from parsed row data."""
        manufacturer, _ = Manufacturer.objects.get_or_create(name=r["manufacturer"])
        drone_model, created_model = DroneModel.objects.get_or_create(
            name=r["model_name"],
            defaults={"manufacturer": manufacturer},
        )
        if created_model:
            self.stdout.write(self.style.WARNING(f"    створено DroneModel: {drone_model}"))

        # power_template: reuse from same model's existing type, else first available
        existing_type = (
            FPVDroneType.objects.filter(model=drone_model).select_related("power_template").first()
            or OpticalDroneType.objects.filter(model=drone_model).select_related("power_template").first()
        )
        power_template = existing_type.power_template if existing_type else PowerTemplate.objects.order_by("pk").first()
        if power_template is None:
            self.stdout.write(self.style.ERROR(f"    PowerTemplate не знайдено — пропускаємо {r['model_name']}"))
            return None

        if r["kind"] == "optical" and r["video_obj"] is None:
            self.stdout.write(self.style.ERROR(
                f"    video_template відсутній для Optical — пропускаємо {r['model_name']}"
            ))
            return None

        common = dict(
            model=drone_model,
            purpose=r["purpose"],
            prop_size=r["prop_size"],
            power_template=power_template,
            has_thermal=r["has_thermal"],
            notes=r["notes"] or "",
        )
        if r["kind"] == "fpv":
            drone_type = FPVDroneType.objects.create(**common, video_frequency=r["video_obj"])
        else:
            drone_type = OpticalDroneType.objects.create(**common, video_template=r["video_obj"])

        if r["ctrl_freqs"]:
            drone_type.control_frequencies.set(r["ctrl_freqs"])

        kind_label = "FPVDroneType" if r["kind"] == "fpv" else "OpticalDroneType"
        self.stdout.write(self.style.WARNING(f"    створено {kind_label}: {drone_type} (pk={drone_type.pk})"))
        return drone_type

    def _do_import(self, rows: list[dict], commit: bool) -> None:
        ct_fpv = ContentType.objects.get_for_model(FPVDroneType)
        ct_opt = ContentType.objects.get_for_model(OpticalDroneType)

        workshop = Location.objects.filter(name__in=["Майстерня", "майстерня"]).first()
        if workshop is None:
            self.stdout.write(self.style.WARNING("  Локацію 'Майстерня' не знайдено — current_location буде порожнім."))

        superadmin = User.objects.filter(is_superuser=True).order_by("pk").first()
        if superadmin is None:
            self.stdout.write(self.style.WARNING("  Суперадміна не знайдено — created_by буде порожнім."))

        PURPOSE_TO_ROLE = {
            "Носій":          "Носій",
            "Мінувальник":    "Мінувальник",
            "Перехоплювач":   "Перехоплювач",
            "Бомбардувальник":"Бомбардувальник",
            "Донаведення":    "FPV",
        }
        roles_by_name = {r.name: r for r in DroneRole.objects.all()}

        def _role_for(row) -> DroneRole | None:
            purpose_name = row["purpose"].name if row["purpose"] else None
            if purpose_name == "Ударний":
                role_name = "FPV"
            else:
                role_name = PURPOSE_TO_ROLE.get(purpose_name)
            return roles_by_name.get(role_name)

        total_created = total_skipped = total_missing = 0

        label = "ІМПОРТ" if commit else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(f"─── {label} ───────────────────────────────────────"))

        for r in rows:
            drone_type = self._find_drone_type(r)
            model_label = _fmt_model(r)

            if drone_type is None:
                if commit:
                    drone_type = self._create_drone_type(r)
                    if drone_type is None:
                        total_missing += 1
                        continue
                else:
                    self.stdout.write(
                        f"  + буде створено тип і {r['qty']}  {model_label}"
                    )
                    total_created += r["qty"]
                    continue

            ct = ct_fpv if r["kind"] == "fpv" else ct_opt
            existing = UAVInstance.objects.filter(
                content_type=ct, object_id=drone_type.pk
            ).exclude(status="deleted").count()

            target = r["qty"]
            to_create = target - existing

            if to_create <= 0:
                self.stdout.write(f"  — пропущено  {model_label}  (вже {existing}/{target})")
                total_skipped += 1
                continue

            if commit:
                role = _role_for(r)
                uav_status = "deferred" if r["deferred"] else "inspection"
                new_uavs = UAVInstance.objects.bulk_create([
                    UAVInstance(
                        content_type=ct,
                        object_id=drone_type.pk,
                        status=uav_status,
                        current_location=workshop,
                        role=role,
                        created_by=superadmin,
                        notes=r["notes"] or "",
                    )
                    for _ in range(to_create)
                ])
                components = []
                for uav in new_uavs:
                    components.append(Component(
                        kind="battery",
                        power_template=drone_type.power_template,
                        assigned_to_uav=uav,
                        status="in_use",
                    ))
                    if r["kind"] == "optical":
                        components.append(Component(
                            kind="spool",
                            video_template=drone_type.video_template,
                            assigned_to_uav=uav,
                            status="in_use",
                        ))
                Component.objects.bulk_create(components)
                kit_label = "батарея + котушка" if r["kind"] == "optical" else "батарея"
                role_label = role.name if role else "—"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ створено {to_create}  {model_label}"
                        f"  (комплект: {kit_label}, роль: {role_label})"
                    )
                )
            else:
                self.stdout.write(
                    f"  + буде створено {to_create}  {model_label}  (вже {existing}/{target})"
                )
            total_created += to_create

        self.stdout.write("")
        action = "Створено" if commit else "Буде створено"
        self.stdout.write(
            f"{action}: {total_created}  |  Пропущено: {total_skipped}  |  Тип не знайдено: {total_missing}"
        )
        if not commit:
            self.stdout.write(self.style.WARNING("  Запустіть з --commit щоб зберегти зміни."))

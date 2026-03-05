from django.core.management.base import BaseCommand

from equipment_accounting.models import FPVDroneType, OpticalDroneType


SECTIONS_FPV = [
    ("ДЕНЬ",             {"purpose__in": [1], "has_thermal": False},
     lambda t: t.notes not in ("учбові", "волонт. не офіц",
                                "волонт. без батарей не перекл.каналы (УЧЕБНЫЕ)",
                                "розстріл") and "цифра" not in t.notes or t.notes == "цифра"),
]


def _ctrl(fpv_type):
    freqs = fpv_type.control_frequencies.all()
    return "-".join(str(f) for f in freqs) if freqs else ""


def _video_fpv(fpv_type):
    return str(fpv_type.video_frequency) if fpv_type.video_frequency else ""


def _video_opt(opt_type):
    return str(opt_type.video_template) if opt_type.video_template else ""


def _row(manufacturer, model, prop, ctrl, video, notes, qty):
    return f"{manufacturer}_{model}_{prop}_{ctrl}_{video}_{notes}_{qty}"


class Command(BaseCommand):
    help = "List all drone types in the verification format: виробник_модель_пропи_ctrl_відео_примітки_кількість"

    def add_arguments(self, parser):
        parser.add_argument(
            "--section",
            choices=["fpv", "optical", "all"],
            default="all",
            help="Which types to show (default: all)",
        )

    def handle(self, *args, **options):
        section = options["section"]

        if section in ("fpv", "all"):
            self._print_fpv()

        if section in ("optical", "all"):
            self._print_optical()

    # ------------------------------------------------------------------
    def _print_fpv(self):
        purpose_names = {1: "ДЕНЬ", 2: "НОСІЇ", 3: "МІНУВАЛЬНИКИ",
                         4: "ПЕРЕХОПЛЮВАЧІ", 5: "БОМБАРДУВАЛЬНИКИ", 6: "ДОНАВЕДЕННЯ"}
        # Group by (purpose, has_thermal)
        groups = {}
        qs = (
            FPVDroneType.objects
            .select_related("model", "model__manufacturer", "video_frequency", "purpose")
            .prefetch_related("control_frequencies")
            .order_by("purpose__id", "has_thermal", "model__name", "prop_size")
        )
        for t in qs:
            p_id = t.purpose_id
            thermal = t.has_thermal
            key = (p_id, thermal)
            groups.setdefault(key, []).append(t)

        for (p_id, thermal), items in sorted(groups.items()):
            section_label = purpose_names.get(p_id, f"purpose={p_id}")
            night_suffix = " (НІЧ / термал)" if thermal else ""
            self.stdout.write(self.style.SUCCESS(
                f"\n=== {section_label}{night_suffix} ==="
            ))
            self._print_header()
            for t in items:
                name = t.model.name
                self.stdout.write(_row(
                    name,
                    name,
                    f'{t.prop_size}"',
                    _ctrl(t),
                    _video_fpv(t),
                    t.notes,
                    "-",
                ))

    def _print_optical(self):
        self.stdout.write(self.style.SUCCESS("\n=== ОПТИКА ==="))
        self._print_header()
        qs = (
            OpticalDroneType.objects
            .select_related("model", "video_template", "purpose")
            .order_by("model__name", "prop_size", "has_thermal")
        )
        for t in qs:
            name = t.model.name
            notes = ("термал" if t.has_thermal else "") + (
                f" {t.notes}" if t.notes else ""
            ).strip()
            self.stdout.write(_row(
                name,
                name,
                f'{t.prop_size}"',
                "",
                _video_opt(t),
                notes,
                "-",
            ))

    def _print_header(self):
        self.stdout.write(self.style.WARNING(
            "виробник_модель_пропи_ctrl_відео_примітки_кількість"
        ))
        self.stdout.write("-" * 70)

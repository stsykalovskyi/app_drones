"""Make created_by required: assign orphan rows to the first superuser, then
remove null=True and change on_delete to CASCADE."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_created_by(apps, schema_editor):
    """Assign any expense with created_by=NULL to the first superuser."""
    User = apps.get_model("auth", "User")
    Expense = apps.get_model("expense_log", "Expense")
    orphans = Expense.objects.filter(created_by__isnull=True)
    if orphans.exists():
        admin_user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if admin_user is None:
            admin_user = User.objects.order_by("pk").first()
        if admin_user is not None:
            orphans.update(created_by=admin_user)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("expense_log", "0004_alter_expense_receipt"),
    ]

    operations = [
        migrations.RunPython(backfill_created_by, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="expense",
            name="created_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="expenses",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Створив",
            ),
        ),
    ]

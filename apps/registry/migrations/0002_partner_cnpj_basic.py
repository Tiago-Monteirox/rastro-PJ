from django.db import migrations, models
from django.db.models import Q
from django.db.models.functions import Substr


def normalize_partner_cnpj_to_basic(apps, schema_editor):
    partner_snapshot = apps.get_model("registry", "PartnerSnapshot")
    partner_snapshot.objects.exclude(partner_cnpj_basic__isnull=True).exclude(
        partner_cnpj_basic=""
    ).update(partner_cnpj_basic=Substr("partner_cnpj_basic", 1, 8))


class Migration(migrations.Migration):
    dependencies = [("registry", "0001_initial")]

    operations = [
        migrations.RemoveConstraint(
            model_name="partnersnapshot",
            name="reg_partner_snapshot_cnpj_14d",
        ),
        migrations.RenameField(
            model_name="partnersnapshot",
            old_name="partner_cnpj",
            new_name="partner_cnpj_basic",
        ),
        migrations.RunPython(normalize_partner_cnpj_to_basic, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="partnersnapshot",
            name="partner_cnpj_basic",
            field=models.CharField(blank=True, max_length=8, null=True),
        ),
        migrations.AddConstraint(
            model_name="partnersnapshot",
            constraint=models.CheckConstraint(
                condition=Q(partner_cnpj_basic__isnull=True)
                | Q(partner_cnpj_basic="")
                | Q(partner_cnpj_basic__regex=r"^[0-9]{8}$"),
                name="reg_partner_snapshot_cnpj_basic_8d",
            ),
        ),
    ]

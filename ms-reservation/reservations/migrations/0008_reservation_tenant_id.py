from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0007_alter_payment_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="tenant_id",
            field=models.CharField(blank=True, db_index=True, max_length=36, null=True),
        ),
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(fields=["tenant_id", "voyageur"], name="reservatio_tenant__463c8f_idx"),
        ),
        migrations.AddIndex(
            model_name="reservation",
            index=models.Index(fields=["tenant_id", "status"], name="reservatio_tenant__201e3c_idx"),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0030_ip_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='advanced',
            name='adv_boot_scrub',
            field=models.IntegerField(default=7),
        )
    ]

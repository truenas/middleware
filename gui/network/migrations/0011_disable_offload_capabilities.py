from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('network', '0010_auto_20181114_1129'),
    ]

    operations = [
        migrations.AddField(
            model_name='interfaces',
            name='int_disable_offload_capabilities',
            field=models.BooleanField(default=False, verbose_name='Disable offload capabilities'),
        ),
    ]

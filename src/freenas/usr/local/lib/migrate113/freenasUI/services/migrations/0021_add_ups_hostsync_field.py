from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0020_make_lunid_non_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='ups',
            name='ups_hostsync',
            field=models.IntegerField(
                default=15,
                verbose_name='Host Sync',
                help_text='Upsmon will wait up to this many seconds in master '
                          'mode for the slaves to disconnect during a shutdown situation'
            ),
        )
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storage', '0010_auto_20180618_0340'),
    ]

    operations = [
        migrations.AddField(
            model_name='disk',
            name='disk_critical',
            field=models.IntegerField(
                blank=True, default=None,
                help_text='Report as critical in the system log and send an email if the temperature is greater or '
                          'equal than N degrees Celsius.',
                null=True, verbose_name='Critical',
                editable=False
            ),
        ),
        migrations.AddField(
            model_name='disk',
            name='disk_difference',
            field=models.IntegerField(
                blank=True, default=None,
                help_text='Report if the temperature has changed by at least N degrees Celsius since the last report.',
                null=True, verbose_name='Difference',
                editable=False
            ),
        ),
        migrations.AddField(
            model_name='disk',
            name='disk_informational',
            field=models.IntegerField(
                blank=True, default=None,
                help_text='Report as informational in the system log if the temperature is greater or equal than N '
                          'degrees Celsius.',
                null=True, verbose_name='Informational',
                editable=False
            ),
        )
    ]

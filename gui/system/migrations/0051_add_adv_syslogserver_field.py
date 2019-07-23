from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0050_add_adv_sysloglevel_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='advanced',
            name='adv_syslogserver',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Specifies the server and port syslog messages will be sent to.  The accepted format is hostname:port or ip:port, if :port is not specified it will default to port 514 (this field currently only takes IPv4 addresses)',  # noqa
                max_length=120,
                verbose_name='Syslog server'
            ),
        ),
    ]

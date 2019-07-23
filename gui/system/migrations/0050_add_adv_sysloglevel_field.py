from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0049_guihttpsprotocols'),
    ]

    operations = [
        migrations.AddField(
            model_name='advanced',
            name='adv_sysloglevel',
            field=models.CharField(
                choices=[
                    ('f_emerg', 'Emergency'),
                    ('f_alert', 'Alert'),
                    ('f_crit', 'Critical'),
                    ('f_err', 'Error'),
                    ('f_warning', 'Warning'),
                    ('f_notice', 'Notice'),
                    ('f_info', 'Info'),
                    ('f_debug', 'Debug'),
                    ('f_is_debug', 'Is_Debug')
                ],
                default='f_info',
                help_text='Specifies which messages will be logged by server. INFO and VERBOSE log transactions that server performs on behalf of the client. f_is_debug specify higher levels of debugging output. The default is f_info.',  # noqa
                max_length=120,
                verbose_name='Syslog level'
            ),
        ),
    ]

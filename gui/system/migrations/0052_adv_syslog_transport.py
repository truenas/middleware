from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0051_move_syslog'),
    ]

    operations = [
        migrations.AddField(
            model_name='advanced',
            name='adv_syslog_transport',
            field=models.CharField(default='UDP', max_length=12),
        ),
        migrations.AddField(
            model_name='advanced',
            name='adv_syslog_tls_certificate',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='system.Certificate'
            ),
        ),
    ]

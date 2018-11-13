from django.db import migrations, models
import freenasUI.freeadmin.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0022_remove_smb_doscharset'),
    ]

    operations = [
        migrations.CreateModel(
            name='NetDataGlobalSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('history', models.IntegerField(default=86400)),
                ('update_every', models.IntegerField(default=1)),
                ('http_port_listen_backlog', models.IntegerField(default=100)),
                ('bind', freenasUI.freeadmin.models.fields.ListField(default=['0.0.0.0', '::'])),
                ('port', models.IntegerField(default=19999)),
                ('additional_params', models.TextField(blank=True, null=True, default='')),
                ('alarms', freenasUI.freeadmin.models.fields.DictField()),
                ('stream_mode', models.CharField(default='NONE', max_length=10)),
                ('api_key', models.CharField(blank=True, max_length=64, null=True)),
                ('destination', freenasUI.freeadmin.models.fields.ListField(blank=True, null=True)),
                ('allow_from', freenasUI.freeadmin.models.fields.ListField(blank=True, default=['*'], null=True)),
            ],
            options={
                'verbose_name': 'Netdata Global Settings',
            },
        )
    ]

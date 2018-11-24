from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0021_add_ups_hostsync_field'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='CIFS',
            name='cifs_srv_doscharset',
        )
    ]

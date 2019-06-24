from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0033_ups_shutdowncmd'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='CIFS',
            name='cifs_srv_nullpw',
        ),
        migrations.RemoveField(
            model_name='CIFS',
            name='cifs_srv_hostlookup',
        ),
        migrations.RemoveField(
            model_name='CIFS',
            name='cifs_srv_domain_logons',
        ),
        migrations.RemoveField(
            model_name='CIFS',
            name='cifs_srv_timeserver',
        ),
        migrations.RemoveField(
            model_name='CIFS',
            name='cifs_srv_allow_execute_always',
        ),
        migrations.RemoveField(
            model_name='CIFS',
            name='cifs_srv_obey_pam_restrictions',
        ),
        migrations.RemoveField(
            model_name='CIFS',
            name='cifs_srv_unixext',
        ),
    ]

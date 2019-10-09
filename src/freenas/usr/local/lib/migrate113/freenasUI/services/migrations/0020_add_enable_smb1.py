from django.db import migrations, models


def move_sysctl_min_protocol(apps, schemaeditor):
    tunables = apps.get_model('system', 'tunable')
    smb1_sysctl = tunables.objects.filter(tun_type='sysctl',
                                          tun_var='freenas.services.smb.config.server_min_protocol',
                                          tun_value='NT1')

    cifs = apps.get_model('services', 'cifs').objects.order_by('-id')[0]

    if smb1_sysctl.exists():
        cifs.cifs_srv_enable_smb1 = True
        cifs.save()
        smb1_sysctl.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0019_add_asigra_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='cifs',
            name='cifs_srv_enable_smb1',
            field=models.BooleanField(default=False,
                help_text=(
                    'Use this option to allow legacy SMB clients to connect to the '
                    'server. Note that SMB1 is being deprecated and it is advised '
                    'to upgrade clients to operating system versions that support '
                    'modern versions of the SMB protocol.'
                ),
                verbose_name='Enable SMB1'
            ),
        ),
        migrations.RunPython(
            move_sysctl_min_protocol
        ),
    ]


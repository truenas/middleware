from django.db import migrations, models

def migrate_unified_config(apps, schema_editor):
    cifs = apps.get_model('services', 'cifs').objects.order_by('-id')[0]
    ngc = apps.get_model('network', 'GlobalConfiguration').objects.all()[0]

    if cifs.cifs_srv_netbiosname == cifs.cifs_srv_netbiosname_b:
        if not ngc.gc_hostname_virtual:
            ngc.gc_hostname_virtual = cifs.cifs_srv_netbiosname
            cifs.cifs_srv_netbiosname = f'{cifs.cifs_srv_netbiosname}_a'
            cifs.cifs_srv_netbiosname_b = f'{cifs.cifs_srv_netbiosname}_b'
            ngc.save()
            cifs.save()

class Migration(migrations.Migration):
    dependencies = [
        ('truenas', '0004_customerinformation'),
    ]

    operations = [
        migrations.RunPython(migrate_unified_config, reverse_code=migrations.RunPython.noop),
    ]

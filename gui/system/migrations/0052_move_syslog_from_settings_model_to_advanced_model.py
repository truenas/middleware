from django.db import migrations


def move_syslog(apps, schema_editor):
    """Move syslog options from Settings model to Advanced model"""
    try:
        Advanced = apps.get_model('system', 'Advanced')
        Settings = apps.get_model('system', 'Settings')
    except LookupError:
        Advanced = None
        Settings = None

    if Advanced and Settings:
        try:
            settings = Settings.objects.latest('id')
            advanced = Advanced.objects.latest('id')
        except Settings.DoesNotExist:
            settings = None  # there is no 'settings' record in DB
        except Advanced.DoesNotExist:
            advanced = Advanced.objects.create()
        finally:
            if settings:
                advanced.adv_sysloglevel = settings.stg_sysloglevel
                advanced.adv_syslogserver = settings.stg_syslogserver
                advanced.save()


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0051_add_adv_syslogserver_field'),
    ]

    operations = [
        migrations.RunPython(move_syslog),
    ]

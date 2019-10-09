import django.core.validators
from django.db import migrations, models

def remove_dc(apps, schema_editor):
    services = apps.get_model("services", "services")
    domaincontroller = services.objects.get(srv_service="domaincontroller")
    try:
        domaincontroller.delete()
    except Exception as error:
        print(f"ERROR: unable to remove domaincontroller service: {error}", file=sys.stderr)

class Migration(migrations.Migration):

    dependencies = [
        ('services', '0026_delete_vm_kmem_size_tunable'),
    ]

    operations = [
        migrations.DeleteModel(
            name='DomainController',
        ),
        migrations.RunPython(
            remove_dc,
        )
    ]

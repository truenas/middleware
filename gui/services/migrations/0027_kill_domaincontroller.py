import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0026_delete_vm_kmem_size_tunable'),
    ]

    operations = [
        migrations.DeleteModel(
            name='DomainController',
        ),
    ]

import django.core.validators
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('services', '0028_merge_20190316_0802'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ServiceMonitor',
        ),
    ]

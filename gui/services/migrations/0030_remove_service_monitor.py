import django.core.validators
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('services', '0029_merge_20190410_0351'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ServiceMonitor',
        ),
    ]

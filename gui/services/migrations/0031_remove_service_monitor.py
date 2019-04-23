import django.core.validators
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('services', '0030_merge_20190422_0554'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ServiceMonitor',
        ),
    ]

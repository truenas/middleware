from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0012_merge_20190108_1040'),
    ]

    operations = [
        migrations.AddField(
            model_name='initshutdown',
            name='ini_timeout',
            field=models.IntegerField(
                default=10,
                verbose_name='Timeout',
                help_text='Automatically stop the script or command after the specified seconds.'
            ),
        ),
    ]

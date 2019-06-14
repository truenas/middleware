from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0013_init_tasks_timeout'),
    ]

    operations = [
        migrations.AddField(
            model_name='initshutdown',
            name='ini_comment',
            field=models.CharField(
                verbose_name='Comment',
                blank=True,
                max_length=255,
            ),
        ),
    ]

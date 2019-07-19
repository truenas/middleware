from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0014_ini_comment_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='initshutdown',
            name='ini_script_text',
            field=models.TextField(blank=True, verbose_name='Script text'),
        ),
    ]

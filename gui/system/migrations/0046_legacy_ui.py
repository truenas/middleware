from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0045_fromname'),
    ]

    operations = [
        migrations.AddField(
            model_name='Advanced',
            name='adv_legacy_ui',
            field=models.BooleanField(
                default=False,
                help_text='Enable or disable the legacy UI.',
                verbose_name='Enable legacy UI'
            ),
        )
    ]

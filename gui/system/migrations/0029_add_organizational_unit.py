from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0028_cert_serials'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificate',
            name='cert_organizational_unit',
            field=models.CharField(
                blank=True, help_text='Organizational unit of the entity',
                max_length=120, null=True, verbose_name='Organizational Unit'
            ),
        ),
        migrations.AddField(
            model_name='certificateauthority',
            name='cert_organizational_unit',
            field=models.CharField(
                blank=True, help_text='Organizational unit of the entity',
                max_length=120, null=True, verbose_name='Organizational Unit'
            ),
        )
    ]

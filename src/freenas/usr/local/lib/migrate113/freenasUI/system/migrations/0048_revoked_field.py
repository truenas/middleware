from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0047_2fa_authentication'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificate',
            name='cert_revoked_date',
            field=models.DateTimeField(
                verbose_name='Revoked Date',
                null=True
            )
        ),
        migrations.AddField(
            model_name='certificateauthority',
            name='cert_revoked_date',
            field=models.DateTimeField(
                verbose_name='Revoked Date',
                null=True
            )
        )
    ]

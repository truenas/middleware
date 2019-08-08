from django.db import migrations, models

import freenasUI.freeadmin.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0046_legacy_ui'),
    ]

    operations = [
        migrations.CreateModel(
            name='TwoFactorAuthentication',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('otp_digits', models.IntegerField(default=6, verbose_name='OTP Digits')),
                ('secret', models.CharField(default=None, max_length=16, null=True)),
                ('window', models.IntegerField(default=0, verbose_name='Counter Value Window')),
                ('interval', models.IntegerField(default=30, verbose_name='TOTP Valid Interval')),
                ('services', freenasUI.freeadmin.models.fields.DictField(default={}, verbose_name='Services')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled'))
            ],
            options={
                'verbose_name': 'Two Factor Authentication',
            },
        )
    ]

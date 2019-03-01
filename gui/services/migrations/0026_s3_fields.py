from django.db import migrations, models
import freenasUI.freeadmin.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0025_merge_20190114_1159'),
    ]

    operations = [
        migrations.AlterField(
            model_name='s3',
            name='s3_access_key',
            field=models.CharField(
                blank=True,
                default='',
                help_text='S3 username',
                max_length=128,
                verbose_name='Access key of 5 to 20 characters in length'
            ),
        ),
        migrations.AlterField(
            model_name='s3',
            name='s3_disks',
            field=freenasUI.freeadmin.models.fields.PathField(
                default='',
                help_text='S3 filesystem directory',
                max_length=255,
                verbose_name='Disks'
            ),
        ),
        migrations.AlterField(
            model_name='s3',
            name='s3_secret_key',
            field=models.CharField(
                blank=True,
                default='',
                help_text='S3 password',
                max_length=128,
                verbose_name='Secret key of 8 to 40 characters in length'
            ),
        ),
    ]

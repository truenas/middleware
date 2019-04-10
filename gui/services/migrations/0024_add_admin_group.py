from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('services', '0023_merge_20190114_2056'),
    ]

    operations = [
        migrations.AddField(
            model_name='cifs',
            name='cifs_srv_admin_group',
            field=models.CharField(blank=True,
                null=True,
                max_length=120,
                help_text=(
                    'Members of this group are local admins and automatically '
                    'have privileges to take ownership of any file in an SMB '
                    'share, reset permissions, and administer the SMB server '
                    'through the Computer Management MMC snap-in.'
                ),
                verbose_name='SMB Administrators Group'),
        ),
    ]

from __future__ import unicode_literals

from django.db import migrations, models

def migrate_shadowcopies(apps, schema_editor):
    SMB_Share = apps.get_model('sharing', 'cifs_share')
    for row in SMB_Share.objects.all():
        row.cifs_shadowcopy = True if row.cifs_storage_task_id else False
        row.save()

class Migration(migrations.Migration):

    dependencies = [
        ('sharing', '0014_add_smb_timemachine'),
    ]

    operations = [
        migrations.AddField(
            model_name='cifs_share',
            name='cifs_shadowcopy',
            field=models.BooleanField(default=False, verbose_name='Enable Shadow Copies'),
        ),
        migrations.RunPython(
            migrate_shadowcopies
        ),
        migrations.RemoveField(
            model_name='cifs_share',
            name='cifs_storage_task_id',
        ),
    ]

from __future__ import unicode_literals
from django.db import migrations, models
import uuid


def add_vuid(apps, schema_editor):
    AFP_Share = apps.get_model('sharing', 'afp_share')
    for row in AFP_Share.objects.all():
        row.afp_vuid = str(uuid.uuid4()) if row.afp_timemachine else ''
        row.save()


class Migration(migrations.Migration):

    dependencies = [
        ('sharing', '0017_add_share_acl'),
    ]

    operations = [
        migrations.AddField(
            model_name='afp_share',
            name='afp_vuid',
            field=models.CharField(
                blank=True,
                help_text='Volume UUID for _adisk._tcp. mDNS advertisment',
                max_length=36,
                verbose_name='Volume UUID'
            )
        ),
        migrations.RunPython(add_vuid, reverse_code=migrations.RunPython.noop),
    ]

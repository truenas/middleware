from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0035_vmware_snapshot_alert'),
    ]

    operations = [
        migrations.RemoveField(
            model_name=model,
            name=f'cert_{name}',
        )
        for model in ('certificate', 'certificateauthority')
        for name in [
            'key_length', 'digest_algorithm', 'lifetime', 'country', 'state', 'city',
            'organization', 'organizational_unit', 'email', 'common', 'san', 'serial', 'chain'
        ]
    ]

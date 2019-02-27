from django.db import migrations, models
import django.db.models.deletion

import datetime

CERT_TYPE_EXISTING = 0x08
affected_models = {
    'activedirectory': {
        'field': 'ad_certificate'
    },
    'idmap_ldap': {
        'field': 'idmap_ldap_certificate'
    },
    'idmap_rfc2307': {
        'field': 'idmap_rfc2307_certificate'
    },
    'ldap': {
        'field': 'ldap_certificate'
    }
}


def save_cas(apps, schema_editor):
    for model_name in affected_models:
        model = apps.get_model('directoryservice', model_name).objects.order_by('-id')
        field = affected_models[model_name]['field']
        if model and getattr(model[0], field):
            affected_models[model_name]['ca_id'] = getattr(model[0], field).id
            setattr(model[0], field, None)
            model[0].save()


def migrate_cas_to_certs(apps, schema_editor):
    cert_model = apps.get_model('system', 'certificate')
    ca_model = apps.get_model('system', 'certificateauthority')
    for model_name in filter(
        lambda i: affected_models[i].get('ca_id'),
        affected_models
    ):
        obj = apps.get_model('directoryservice', model_name).objects.order_by('-id')[0]
        ca = ca_model.objects.get(pk=affected_models[model_name]['ca_id'])
        setattr(
            obj,
            affected_models[model_name]['field'],
            cert_model.objects.create(**{
                'cert_name': f'{ca.cert_name} (migrated for {model_name} at {datetime.datetime.now()})',
                'cert_certificate': ca.cert_certificate,
                'cert_privatekey': ca.cert_privatekey,
                'cert_type': CERT_TYPE_EXISTING
            })
        )
        obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('directoryservice', '0005_idmap_ad'),
    ]

    operations = [
        migrations.RunPython(
            save_cas
        ),
        migrations.AlterField(
            model_name='activedirectory',
            name='ad_certificate',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='system.Certificate',
                verbose_name='Certificate',
            ),
        ),
        migrations.AlterField(
            model_name='idmap_ldap',
            name='idmap_ldap_certificate',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='system.Certificate',
                verbose_name='Certificate',
            ),
        ),
        migrations.AlterField(
            model_name='idmap_rfc2307',
            name='idmap_rfc2307_certificate',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='system.Certificate',
                verbose_name='Certificate',
            ),
        ),
        migrations.AlterField(
            model_name='ldap',
            name='ldap_certificate',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='system.Certificate',
                verbose_name='Certificate',
            ),
        ),
        migrations.RunPython(
            migrate_cas_to_certs
        )
    ]

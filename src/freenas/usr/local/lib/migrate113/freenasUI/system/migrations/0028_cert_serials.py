from django.db import migrations

from OpenSSL import crypto


def serial_update(apps, schema_editor):

    certificate_model = apps.get_model('system', 'certificate')
    for cert in certificate_model.objects.all():
        if not cert.cert_serial and cert.cert_certificate:
            try:
                cert.cert_serial = crypto.load_certificate(
                    crypto.FILETYPE_PEM, cert.cert_certificate
                ).get_serial_number()
            except crypto.Error:
                # Let's pass this to ensure very old certificates which might be malformed
                # not raise exceptions
                pass
            else:
                cert.save()


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0027_merge_20180807_0638'),
    ]

    operations = [
        migrations.RunPython(
            serial_update
        )
    ]

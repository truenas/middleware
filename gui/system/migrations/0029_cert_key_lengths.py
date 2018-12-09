from django.db import migrations

from OpenSSL import crypto
import itertools

# FIXME: Talk to william about the best way to handle migrations in different branches


def normalize_key_length(apps, schema_editor):
    # TODO: Talk to William, Perhaps let's remove all the attributes which can be obtained from parsing cert/privatekey

    ca_model = apps.get_model('system', 'certificateauthority')
    certificate_model = apps.get_model('system', 'certificate')
    for cert in itertools.chain(certificate_model.objects.all(), ca_model.objects.all()):
        if cert.cert_privatekey:
            try:
                cert.cert_key_length = crypto.load_privatekey(
                    crypto.FILETYPE_PEM, cert.cert_privatekey
                ).bits()
            except crypto.Error:
                # Let's pass this to ensure very old private keys which might be malformed
                # not raise exceptions
                pass
            else:
                cert.save()


class Migration(migrations.Migration):

    dependencies = [
        ('system', '0028_cert_serials'),
    ]

    operations = [
        migrations.RunPython(
            normalize_key_length
        )
    ]

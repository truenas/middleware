from django.db import migrations, models
import django.db.models.deletion


def add_openvpn_to_services(apps, schema_editor):
    services = apps.get_model('services', 'services')
    for srv in ('openvpn_server', 'openvpn_client'):
        obj = services.objects.create()
        obj.srv_service = srv
        obj.srv_enable = False
        obj.save()


def remove_openvpn_from_services(apps, schema_editor):
    services = apps.get_model('services', 'services')
    for srv in ('openvpn_server', 'openvpn_client'):
        obj = services.objects.get(srv_service=srv)
        obj.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0036_remove_smart_email'),
    ]

    operations = [
        migrations.CreateModel(
            name='OpenVPNClient',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('port', models.IntegerField(default=1194, verbose_name='Port')),
                ('protocol', models.CharField(default='UDP', max_length=4)),
                ('device_type', models.CharField(default='TUN', max_length=4)),
                ('nobind', models.BooleanField(default=True, verbose_name='Nobind')),
                (
                    'authentication_algorithm', models.CharField(
                        max_length=32, null=True, verbose_name='Authentication Algorithm', default='RSA-SHA256'
                    )
                ),
                (
                    'tls_crypt_auth', models.TextField(
                        null=True, blank=True,
                        verbose_name='TLS Crypt Authentication'
                    )
                ),
                ('cipher', models.CharField(max_length=32, null=True, default='AES-256-CBC')),
                ('compression', models.CharField(max_length=32, null=True, default='LZO')),
                ('additional_parameters', models.TextField(default='', verbose_name='Additional Parameters')),
                (
                    'client_certificate', models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                        to='system.Certificate', verbose_name='Client Certificate'
                    )
                ),
                (
                    'root_ca', models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                        to='system.CertificateAuthority', verbose_name='Root Certificate Authority'
                    )
                ),
                ('remote', models.CharField(max_length=120, verbose_name='Remote IP/Domain'))
            ],
            options={
                'verbose_name': 'OpenVPN Client'
            },
        ),
        migrations.CreateModel(
            name='OpenVPNServer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('port', models.IntegerField(default=1194, verbose_name='Port')),
                ('protocol', models.CharField(default='UDP', max_length=4)),
                ('device_type', models.CharField(default='TUN', max_length=4)),
                (
                    'authentication_algorithm', models.CharField(
                        max_length=32, null=True, verbose_name='Authentication Algorithm', default='RSA-SHA256'
                    )
                ),
                (
                    'tls_crypt_auth', models.TextField(
                        null=True, blank=True,
                        verbose_name='TLS Crypt Authentication'
                    )
                ),
                ('cipher', models.CharField(max_length=32, null=True, default='AES-256-CBC')),
                ('compression', models.CharField(max_length=32, null=True, default='LZO')),
                ('additional_parameters', models.TextField(default='', verbose_name='Additional Parameters')),
                (
                    'server_certificate', models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                        to='system.Certificate', verbose_name='Server Certificate'
                    )
                ),
                (
                    'root_ca', models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                        to='system.CertificateAuthority', verbose_name='Root Certificate Authority',
                        related_name='server_root_ca'
                    )
                ),
                ('server', models.CharField(default='10.8.0.0', verbose_name='Server IP', max_length=45)),
                ('topology', models.CharField(max_length=16, null=True, verbose_name='Topology', default='SUBNET')),
                ('netmask', models.IntegerField(default=24, verbose_name='Server Netmask'))
            ],
            options={
                'verbose_name': 'OpenVPN Server'
            },
        ),
        migrations.RunPython(
            add_openvpn_to_services,
            reverse_code=remove_openvpn_from_services
        )
    ]

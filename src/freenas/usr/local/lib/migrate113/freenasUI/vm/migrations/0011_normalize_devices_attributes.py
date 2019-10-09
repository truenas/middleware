from django.db import migrations, models


def ensure_vnc_port(apps, schema_editor):
    device_model = apps.get_model('vm', 'Device')
    all_ports = [6000, 6100]
    vnc_devices = device_model.objects.filter(dtype='VNC')
    for vnc_device in vnc_devices:
        if vnc_device.attributes.get('vnc_port'):
            try:
                port = int(vnc_device.attributes['vnc_port'])
            except ValueError:
                vnc_device.attributes['vnc_port'] = None
            else:
                if port in all_ports or port < 5900 or port > 65535:
                    vnc_device.attributes['vnc_port'] = None
                else:
                    vnc_device.attributes['vnc_port'] = port
                    all_ports.append(port)

    for vnc_device in vnc_devices:
        if not vnc_device.attributes.get('vnc_port'):
            port = next((i for i in range(5900, 65535) if i not in all_ports))
            all_ports.append(port)
            vnc_device.attributes['vnc_port'] = port

        if not vnc_device.attributes.get('vnc_bind'):
            # This is to ensure old users have this as a default value
            vnc_device.attributes['vnc_bind'] = '0.0.0.0'

        vnc_device.save()


def add_physical_sector_size_support(apps, schema_editor):
    device_model = apps.get_model('vm', 'Device')
    for device in device_model.objects.filter(dtype__in=['DISK', 'RAW']):
        try:
            sector_size = int(device.attributes.pop('sectorsize', None))
            if sector_size not in [512, 4096]:
                raise ValueError('Invalid sector size')

        except (ValueError, TypeError):
            sector_size = None

        device.attributes.update({
            'logical_sectorsize': sector_size,
            'physical_sectorsize': None,
        })

        device.save()


def normalize_mac_address(apps, schema_editor):
    device_model = apps.get_model('vm', 'Device')
    for nic_device in device_model.objects.filter(dtype='NIC'):
        if not nic_device.attributes.get('mac') or nic_device.attributes['mac'] == '00:a0:98:FF:FF:FF':
            nic_device.attributes['mac'] = None
            nic_device.save()


class Migration(migrations.Migration):

    dependencies = [
        ('vm', '0010_normalize_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='vm',
            name='cores',
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name='vm',
            name='threads',
            field=models.IntegerField(default=1),
        ),
        migrations.RunPython(ensure_vnc_port),
        migrations.RunPython(add_physical_sector_size_support),
        migrations.RunPython(normalize_mac_address),
        migrations.AddField(
            model_name='vm',
            name='shutdown_timeout',
            field=models.IntegerField(default=90),
        ),
    ]

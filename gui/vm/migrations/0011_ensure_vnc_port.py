from django.db import migrations


def ensure_vnc_port(apps, schema_editor):
    device_model = apps.get_model('vm', 'Device')
    all_ports = []
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

        vnc_device.save()


class Migration(migrations.Migration):

    dependencies = [
        ('vm', '0010_normalize_size'),
    ]

    operations = [
        migrations.RunPython(ensure_vnc_port),
    ]

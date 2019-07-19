import math

from django.db import migrations


def convert_size(apps, schema_editor):
    device_model = apps.get_model('vm', 'Device')
    for device in device_model.objects.filter(dtype='RAW'):
        if isinstance(device.attributes.get('size') or 0, str):
            size = original_value = device.attributes['size']
            suffix = original_value[-1]
            if not suffix.isdigit():
                size = original_value[:-1]

            try:
                size = int(size)
            except ValueError:
                # If the value is malformed, we shift it to 1GB
                size = 1

            if suffix == 'T':
                size *= 1024
            elif suffix == 'M':
                size = math.ceil(size / 1024)

            # If we have a suffix other then T/G/B, we disregard it completely following how vm plugin does it
            # and consider size to be in GB now
            device.attributes['size'] = size
            device.save()


class Migration(migrations.Migration):

    dependencies = [
        ('vm', '0009_auto_20190315_1058'),
    ]

    operations = [
        migrations.RunPython(convert_size),
    ]

from django.db import migrations


def convert_size(apps, schema_editor):
    device_model = apps.get_model('vm', 'Device')
    for device in device_model.objects.filter(dtype='RAW'):
        size = device.attributes.get('size')
        if not isinstance(size, int):
            size = original_value = str(device.attributes.get('size') or 1)
            suffix = original_value[-1]
            if not suffix.isdigit():
                size = original_value[:-1]

            try:
                size = int(size)
            except ValueError:
                # If the value is malformed, we shift it to 1GB
                size = 1

            if suffix == 'T':
                size *= (1024 * 1024 * 1024 * 1024)
            elif suffix == 'G' or suffix.isdigit():
                # suffix would be a digit in cases where we only have say "14" saved in db
                size *= (1024 * 1024 * 1024)
            elif suffix == 'M':
                size *= (1024 * 1024)

            # If we have a suffix other then T/G/B, we disregard it completely following how vm plugin does it
            # and consider size to be in GB now
        else:
            # If it's an integer already, it's in GB
            size = size or 1
            size *= (1024 * 1024 * 1024)

        # At this stage size has been converted to bytes
        device.attributes['size'] = size
        device.save()


class Migration(migrations.Migration):

    dependencies = [
        ('vm', '0009_auto_20190315_1058'),
    ]

    operations = [
        migrations.RunPython(convert_size),
    ]

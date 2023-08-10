from .slot_mappings import MAPPINGS


def map_enclosures(enclosures):
    mapped = [{'id': 'mapped_enclosure_0', 'elements': {'Array Device Slot': {}}}]
    jbods = []
    for enclosure in enclosures:
        if not enclosure['controller']:
            jbods.append(enclosure)
            continue

        try:
            mapped_dict = MAPPINGS[enclosure['dmi']]['mapping_info']
        except KeyError:
            # X, M, F series don't need to be mapped so this is expected
            return enclosures

        vers_key = 'DEFAULT'
        if not MAPPINGS[enclosure['dmi']]['any_version']:
            # platforms can have different "versions" which
            # means that they can be ever so slightly cabled
            # differently which leads to us having to map the
            # drives based on how they're cabled
            # (hence the "version")
            for key, vers in mapped_dict['versions'].items():
                if enclosure['revision'] == key:
                    vers_key = vers
                    break

        for key, _dsm in MAPPINGS[enclosure['dmi']]['mapping_info']['versions'][vers_key].items():
            # now that we know what product "version" we're on, we need to be
            # sure and pull the drive mappings based on the enclosures unique
            # (non-changing) id. The non-changing id that uniquely identifies
            # the enclosure is different between each platform
            if (disk_slots_mapping := _dsm.get(enclosure[key])) is not None:
                break
        else:
            raise LookupError(f'Enclosure {enclosure["name"]!r} not found in mapping')

        for orig_slot, orig_info in enclosure['elements']['Array Device Slot'].items():
            mapped_slot = disk_slots_mapping[orig_slot]['mapped_slot']
            mapped[0]['elements']['Array Device Slot'].update({
                mapped_slot: {
                    'descriptor': f'Disk #{mapped_slot}',
                    'status': orig_info['status'],
                    'value': orig_info['value'],
                    'value_raw': orig_info['value_raw'],
                    'dev': orig_info['dev'],
                    'original': {
                        'enclosure_id': enclosure['id'],
                        'enclosure_sg': enclosure['sg'],
                        'enclosure_bsg': enclosure['bsg'],
                        'descriptor': orig_info['descriptor'],
                        'slot': orig_slot
                    }
                }
            })

    return mapped + jbods

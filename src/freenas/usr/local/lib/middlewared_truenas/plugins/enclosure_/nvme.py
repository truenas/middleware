from middlewared.service import Service, private


class EnclosureService(Service):

    @private
    def r50bm_impl(self, slot_to_nvd):
        # R50BM slot location starts at 4 and increments by 1 (i.e. 4, 5, 6 etc)
        # HOWEVER, we "combine" the head-unit with the rear nvme drives on the R50 and R50B
        # platforms. The R50BM has 48 drive slots in the head-unit, so to "combine" this with
        # the disk dictionary for the head-unit, we set the starting mapped slot to 49 and
        # increment accordingly.
        mapping = {
            4: 49,  # slot 4 on OS, mapped to slot 49
            6: 50,  # slot 6 on OS, mapped to slot 50
            5: 51,  # slot 5 on OS, mapped to slot 51
            7: 52,  # slot 7 on OS, mapped to slot 52
        }

        slots = {}
        for orig_slot, mapped_slot in mapping.items():
            if device := slot_to_nvd.get(orig_slot, ''):
                status = 'OK'
                value_raw = 16777216
            else:
                status = 'Not Installed'
                value_raw = 83886080

            slots.update({
                mapped_slot: {
                    'descriptor': f'Disk #{mapped_slot}',
                    'status': status,
                    'value': 'None',
                    'value_raw': value_raw,
                    'dev': device,
                    'original': {
                        'enclosure_id': None,
                        'number': None,
                        'slot': None,
                    }
                }
            })

        return slots

    @private
    def mseries_impl(self, count, slot_to_nvd):
        slots = {}
        for slot in range(1, 1 + count):
            device = slot_to_nvd.get(slot, '')
            if device:
                status = 'OK'
                value_raw = 16777216
            else:
                status = 'Not Installed'
                value_raw = 83886080

            slots.update({
                slot: {
                    'descriptor': f'Disk #{slot}',
                    'status': status,
                    'value': 'None',
                    'value_raw': value_raw,
                    'dev': device,
                }
            })

        return slots

    @private
    def fake_nvme_enclosure(self, id, name, model, count, slot_to_nvd):
        slots = self.r50bm_impl(slot_to_nvd) if model == 'R50BM' else self.mseries_impl(count, slot_to_nvd)
        return [{
            'id': id,
            'number': 1,
            'name': name,
            'label': name,
            'model': model,
            'controller': True,
            'has_slot_status': False,
            'elements': {'Array Device Slot': slots},
        }]

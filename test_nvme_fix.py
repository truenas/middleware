#!/usr/bin/env python3
"""Test script to verify the V-series NVMe enclosure mapping fix."""

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'src/middlewared'))

from middlewared.plugins.enclosure_.nvme2 import map_nvme

def test_nvme_mapping():
    print("=" * 80)
    print("Testing V-series NVMe Enclosure Mapping Fix")
    print("=" * 80)
    print()

    try:
        result = map_nvme()

        if not result:
            print("ERROR: map_nvme() returned empty list!")
            return False

        print(f"Enclosures found: {len(result)}")
        print()

        for enclosure in result:
            print(f"Enclosure ID: {enclosure['id']}")
            print(f"  Model: {enclosure['model']}")
            print(f"  Name: {enclosure['name']}")
            print(f"  Status: {enclosure['status']}")
            print()

            if 'Array Device Slot' in enclosure['elements']:
                slots = enclosure['elements']['Array Device Slot']
                print(f"  Detected {len(slots)} slots:")
                print()

                for slot_num, slot_info in sorted(slots.items()):
                    status = slot_info['status']
                    device = slot_info['dev']
                    descriptor = slot_info['descriptor']

                    if device:
                        print(f"    Slot {slot_num}: ✓ {status:15s} - {device:10s} ({descriptor})")
                    else:
                        print(f"    Slot {slot_num}: ✗ {status:15s} - (empty)       ({descriptor})")

        print()
        print("=" * 80)

        # Verify that at least some slots are populated
        populated_count = 0
        for enclosure in result:
            if 'Array Device Slot' in enclosure['elements']:
                slots = enclosure['elements']['Array Device Slot']
                for slot_info in slots.values():
                    if slot_info['dev'] is not None:
                        populated_count += 1

        if populated_count > 0:
            print(f"✓ SUCCESS: {populated_count} slot(s) properly mapped to NVMe devices")
            return True
        else:
            print("✗ FAILURE: No slots are populated (mapping still broken)")
            return False

    except Exception as e:
        print(f"ERROR: Exception occurred during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_nvme_mapping()
    sys.exit(0 if success else 1)

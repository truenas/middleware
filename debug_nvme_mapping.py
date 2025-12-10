#!/usr/bin/env python3
"""Debug script to investigate NVMe enclosure mapping issues on V140/V160 systems."""

import pathlib
import re
from pyudev import Context, Devices, DeviceNotFoundAtPathError

RE_SLOT = re.compile(r'^0-([0-9]+)$')

def debug_nvme_mapping():
    ctx = Context()

    print("=" * 80)
    print("DEBUG: NVMe Enclosure Mapping for V140/V160")
    print("=" * 80)

    # Step 1: Check PCIe slot addresses
    print("\n[1] PCIe Slot Addresses from /sys/bus/pci/slots:")
    print("-" * 80)
    slot_path = pathlib.Path('/sys/bus/pci/slots')
    if slot_path.exists():
        addresses_to_slots = {}
        for slot in slot_path.iterdir():
            addr_file = slot / 'address'
            if addr_file.exists():
                addr = addr_file.read_text().strip()
                addresses_to_slots[addr] = slot.name
                print(f"  Slot: {slot.name:20s} -> Address: {addr}")
        print(f"\nTotal slots found: {len(addresses_to_slots)}")
    else:
        print("  ERROR: /sys/bus/pci/slots does not exist!")
        addresses_to_slots = {}

    # Step 2: Check for ACPI device with path \\_SB_.PC03.BR3A
    print("\n[2] ACPI Devices (looking for PLX bridge: \\_SB_.PC03.BR3A):")
    print("-" * 80)
    target_path = b'\\_SB_.PC03.BR3A'
    acpi_devices = list(ctx.list_devices(subsystem='acpi'))
    print(f"  Total ACPI devices: {len(acpi_devices)}")

    found_target = False
    for device in acpi_devices:
        path = device.attributes.get('path')
        if path == target_path:
            found_target = True
            print(f"  ✓ FOUND TARGET: {path.decode() if path else 'None'}")
            print(f"    sys_path: {device.sys_path}")

            # Try to get physical_node
            phys_node_path = f'{device.sys_path}/physical_node'
            print(f"    Checking for physical_node at: {phys_node_path}")
            try:
                physical_node = Devices.from_path(ctx, phys_node_path)
                print(f"    ✓ physical_node found: {physical_node.sys_name}")

                # List children
                print(f"\n    Children of physical_node:")
                children_count = 0
                block_children_count = 0
                for child in physical_node.children:
                    children_count += 1
                    subsys = child.properties.get('SUBSYSTEM')
                    if subsys == 'block':
                        block_children_count += 1
                        print(f"      - {child.sys_name:15s} (subsystem: {subsys})")

                        # Try to get parent info
                        try:
                            parent = child.parent
                            print(f"          parent: {parent.sys_name if parent else 'None'}")
                            if parent:
                                grandparent = parent.parent
                                print(f"          grandparent: {grandparent.sys_name if grandparent else 'None'}")

                                if grandparent:
                                    controller_sys_name = grandparent.sys_name
                                    pci_addr = controller_sys_name.split('.')[0]
                                    print(f"          PCIe address: {pci_addr}")

                                    # Check if this address is in our slot mapping
                                    slot_name = addresses_to_slots.get(pci_addr)
                                    print(f"          Slot name: {slot_name}")

                                    if slot_name:
                                        m = re.match(RE_SLOT, slot_name)
                                        if m:
                                            slot_num = int(m.group(1))
                                            print(f"          ✓ MAPPED TO SLOT: {slot_num}")
                                        else:
                                            print(f"          ✗ Slot name doesn't match pattern: {slot_name}")
                                    else:
                                        print(f"          ✗ PCIe address not in slot mapping")
                        except AttributeError as e:
                            print(f"          ✗ Error getting parent info: {e}")

                print(f"\n    Total children: {children_count}, Block devices: {block_children_count}")

            except DeviceNotFoundAtPathError:
                print(f"    ✗ physical_node NOT FOUND at {phys_node_path}")
            except Exception as e:
                print(f"    ✗ Error: {e}")

    if not found_target:
        print(f"  ✗ TARGET ACPI PATH NOT FOUND: {target_path.decode()}")
        print(f"\n  Available ACPI paths (showing first 50):")
        for i, device in enumerate(acpi_devices[:50]):
            path = device.attributes.get('path')
            if path:
                print(f"    {path.decode()}")

    # Step 3: List all NVMe block devices
    print("\n[3] All NVMe Block Devices:")
    print("-" * 80)
    nvme_devices = []
    for device in ctx.list_devices(subsystem='block'):
        if device.sys_name.startswith('nvme') and 'n' in device.sys_name:
            nvme_devices.append(device)
            print(f"  Device: {device.sys_name}")
            print(f"    sys_path: {device.sys_path}")

            # Get parent info
            try:
                parent = device.parent
                if parent:
                    print(f"    parent: {parent.sys_name} (subsystem: {parent.subsystem})")
                    grandparent = parent.parent
                    if grandparent:
                        print(f"    grandparent: {grandparent.sys_name} (subsystem: {grandparent.subsystem})")
                        if grandparent.parent:
                            print(f"    great-grandparent: {grandparent.parent.sys_name}")
            except Exception as e:
                print(f"    Error getting parent info: {e}")

            # Check ACPI path
            current = device
            depth = 0
            max_depth = 10
            while current and depth < max_depth:
                if hasattr(current, 'attributes'):
                    acpi_path = current.attributes.get('path')
                    if acpi_path:
                        print(f"    ACPI path at depth {depth}: {acpi_path.decode()}")
                        break
                try:
                    current = current.parent
                    depth += 1
                except:
                    break

            print()

    print(f"Total NVMe devices found: {len(nvme_devices)}")

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    debug_nvme_mapping()

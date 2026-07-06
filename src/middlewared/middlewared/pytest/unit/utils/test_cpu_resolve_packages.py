from middlewared.utils.cpu import _chip_family, _resolve_packages


def test_chip_family():
    assert _chip_family("coretemp-isa-0000") == "coretemp"
    assert _chip_family("k10temp-pci-00c3") == "k10temp"
    assert _chip_family("via_cputemp-isa-0000") == "via_cputemp"
    assert _chip_family("cpu_thermal-virtual-0") == "cpu_thermal"


def test_coretemp_uses_package_label():
    chips = {"coretemp-isa-0000": {"Package id 0": 40.0, "Core 0": 50.0}}
    assert _resolve_packages(chips) == {"coretemp-isa-0000": 0}


def test_coretemp_package_label_wins_over_suffix():
    # suffix would say 0, but the kernel label says 3
    chips = {"coretemp-isa-0000": {"Package id 3": 40.0, "Core 0": 50.0}}
    assert _resolve_packages(chips) == {"coretemp-isa-0000": 3}


def test_coretemp_dual_socket_by_label():
    chips = {
        "coretemp-isa-0000": {"Package id 0": 36.0, "Core 0": 48.0},
        "coretemp-isa-0001": {"Package id 1": 45.0, "Core 0": 55.0},
    }
    assert _resolve_packages(chips) == {"coretemp-isa-0000": 0, "coretemp-isa-0001": 1}


def test_coretemp_falls_back_to_hex_suffix():
    # no Package id label -> parse the ISA suffix (hex)
    chips = {"coretemp-isa-0001": {"Core 0": 50.0}}
    assert _resolve_packages(chips) == {"coretemp-isa-0001": 1}


def test_k10temp_single_socket_is_zero():
    chips = {"k10temp-pci-00c3": {"Tctl": 50.0}}
    assert _resolve_packages(chips) == {"k10temp-pci-00c3": 0}


def test_k10temp_dual_socket_alphabetical_index():
    chips = {
        "k10temp-pci-00c3": {"Tctl": 60.0},
        "k10temp-pci-00cb": {"Tctl": 70.0},
    }
    assert _resolve_packages(chips) == {"k10temp-pci-00c3": 0, "k10temp-pci-00cb": 1}


def test_k10temp_alphabetical_index_is_pci_order_not_socket_truth():
    # Package index follows PCI-address sort order, which is a fallback for the
    # numa_node libsensors does not expose. If firmware enumerated socket 1 at
    # the lexicographically-smaller PCI address, the two sockets' per-core temps
    # would swap (aggregate is unaffected).
    chips = {
        "k10temp-pci-00cb": {"Tctl": 70.0},
        "k10temp-pci-00c3": {"Tctl": 60.0},
    }
    assert _resolve_packages(chips) == {"k10temp-pci-00c3": 0, "k10temp-pci-00cb": 1}


def test_generic_chips_are_package_zero():
    chips = {
        "via_cputemp-isa-0000": {"temp1": 55.0},
        "cpu_thermal-virtual-0": {"temp1": 60.0},
    }
    assert _resolve_packages(chips) == {
        "via_cputemp-isa-0000": 0,
        "cpu_thermal-virtual-0": 0,
    }

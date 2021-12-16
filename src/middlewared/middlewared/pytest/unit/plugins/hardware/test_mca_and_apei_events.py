from middlewared.plugins.hardware_.mca_and_apei_events import HardwareService
from middlewared.service import Service

OBJ = HardwareService(Service)


def test__unique_mca_events():
    unique_mca_events = ("""
    MCA: CPU 39 COR (1) MS channel 1 memory error
    MCA: CPU 0 COR (1) RD channel 0 memory error
    MCA: CPU 2 UNCOR PCC RD channel 0 memory error
    MCA: CPU 0 COR (1) GCACHE L2 EVICT error
    MCA: CPU 0 COR (1) ICACHE L2 IRD error
    MCA: CPU 0 COR (1) DCACHE L2 DRD error
    MCA: CPU 6 COR (1) DCACHE L1 DRD error
    MCA: CPU 6 COR (1) ICACHE L1 IRD error
    MCA: CPU 6 COR (2) OVER GCACHE L1 EVICT error
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [
            'MCA: CPU 39 COR (1) MS channel 1 memory error',
            'MCA: CPU 0 COR (1) RD channel 0 memory error',
            'MCA: CPU 2 UNCOR PCC RD channel 0 memory error',
            'MCA: CPU 0 COR (1) GCACHE L2 EVICT error',
            'MCA: CPU 0 COR (1) ICACHE L2 IRD error',
            'MCA: CPU 0 COR (1) DCACHE L2 DRD error',
            'MCA: CPU 6 COR (1) DCACHE L1 DRD error',
            'MCA: CPU 6 COR (1) ICACHE L1 IRD error',
            'MCA: CPU 6 COR (2) OVER GCACHE L1 EVICT error',
        ],
        'APEI_EVENTS': [],
    }
    events = OBJ._parse_msgbuf(msgbuf=unique_mca_events)
    assert events == expected_result


def test__duplicate_mca_events():
    duplicate_mca_events = ("""
    MCA: CPU 39 COR (1) MS channel 1 memory error
    MCA: CPU 0 COR (1) RD channel 0 memory error
    MCA: CPU 2 UNCOR PCC RD channel 0 memory error
    MCA: CPU 0 COR (1) GCACHE L2 EVICT error
    MCA: CPU 0 COR (1) ICACHE L2 IRD error
    MCA: CPU 0 COR (1) DCACHE L2 DRD error
    MCA: CPU 6 COR (1) DCACHE L1 DRD error
    MCA: CPU 6 COR (1) ICACHE L1 IRD error
    MCA: CPU 6 COR (2) OVER GCACHE L1 EVICT error
    MCA: CPU 39 COR (1) MS channel 1 memory error
    MCA: CPU 0 COR (1) RD channel 0 memory error
    MCA: CPU 2 UNCOR PCC RD channel 0 memory error
    MCA: CPU 0 COR (1) GCACHE L2 EVICT error
    MCA: CPU 0 COR (1) ICACHE L2 IRD error
    MCA: CPU 0 COR (1) DCACHE L2 DRD error
    MCA: CPU 6 COR (1) DCACHE L1 DRD error
    MCA: CPU 6 COR (1) ICACHE L1 IRD error
    MCA: CPU 6 COR (2) OVER GCACHE L1 EVICT error
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [
            'MCA: CPU 39 COR (1) MS channel 1 memory error',
            'MCA: CPU 0 COR (1) RD channel 0 memory error',
            'MCA: CPU 2 UNCOR PCC RD channel 0 memory error',
            'MCA: CPU 0 COR (1) GCACHE L2 EVICT error',
            'MCA: CPU 0 COR (1) ICACHE L2 IRD error',
            'MCA: CPU 0 COR (1) DCACHE L2 DRD error',
            'MCA: CPU 6 COR (1) DCACHE L1 DRD error',
            'MCA: CPU 6 COR (1) ICACHE L1 IRD error',
            'MCA: CPU 6 COR (2) OVER GCACHE L1 EVICT error',
        ],
        'APEI_EVENTS': [],
    }
    events = OBJ._parse_msgbuf(msgbuf=duplicate_mca_events)
    assert events == expected_result


def test__apei_recoverable_memory_event():
    apei_event = ("""
    APEI Recoverable Memory Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Recoverable Memory Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_recoverable_pcie_event():
    apei_event = ("""
    APEI Recoverable PCIe Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Recoverable PCIe Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_recoverable_error_event():
    apei_event = ("""
    APEI Recoverable Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Recoverable Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_fatal_memory_event():
    apei_event = ("""
    APEI Fatal Memory Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Fatal Memory Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_fatal_pcie_event():
    apei_event = ("""
    APEI Fatal PCIe Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Fatal PCIe Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_fatal_event():
    apei_event = ("""
    APEI Fatal Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Fatal Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_corrected_memory_event():
    apei_event = ("""
    APEI Corrected Memory Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Corrected Memory Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_corrected_pcie_event():
    apei_event = ("""
    APEI Corrected PCIe Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Corrected PCIe Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_corrected_event():
    apei_event = ("""
    APEI Corrected Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Corrected Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_informational_memory_event():
    apei_event = ("""
    APEI Informational Memory Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Informational Memory Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_informational_pcie_event():
    apei_event = ("""
    APEI Informational PCIe Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Informational PCIe Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__apei_informational_event():
    apei_event = ("""
    APEI Informational Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [],
        'APEI_EVENTS': [
            {'APEI Informational Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=apei_event)
    assert events == expected_result


def test__mca_and_apei_events():
    unique_mca_events = ("""
    MCA: CPU 39 COR (1) MS channel 1 memory error
    MCA: CPU 0 COR (1) RD channel 0 memory error
    MCA: CPU 2 UNCOR PCC RD channel 0 memory error
    MCA: CPU 0 COR (1) GCACHE L2 EVICT error
    MCA: CPU 0 COR (1) ICACHE L2 IRD error
    MCA: CPU 0 COR (1) DCACHE L2 DRD error
    MCA: CPU 6 COR (1) DCACHE L1 DRD error
    MCA: CPU 6 COR (1) ICACHE L1 IRD error
    MCA: CPU 6 COR (2) OVER GCACHE L1 EVICT error
    """).splitlines()

    apei_event = ("""
    APEI Informational Error:
     Error Status: 0x0
     Physical Address: 0x72aed744c0
     Physical Address Mask: 0x3fffffffffc0
     Node: 2
     Card: 1
     Module: 0
     Device: 15
     Row: 8165
     Column: 184
     Memory Error Type: 2
     Rank Number: 0
     Card Handle: 0xf
     Module Handle: 0x1a
     Bank Group: 3
     Bank Address: 1
     Chip Identification: 0
     Flags: 0x1
     FRU Text: P2-DIMMB1 232891B6
    BOGUS LINE
    """).splitlines()

    expected_result = {
        'MCA_EVENTS': [
            'MCA: CPU 39 COR (1) MS channel 1 memory error',
            'MCA: CPU 0 COR (1) RD channel 0 memory error',
            'MCA: CPU 2 UNCOR PCC RD channel 0 memory error',
            'MCA: CPU 0 COR (1) GCACHE L2 EVICT error',
            'MCA: CPU 0 COR (1) ICACHE L2 IRD error',
            'MCA: CPU 0 COR (1) DCACHE L2 DRD error',
            'MCA: CPU 6 COR (1) DCACHE L1 DRD error',
            'MCA: CPU 6 COR (1) ICACHE L1 IRD error',
            'MCA: CPU 6 COR (2) OVER GCACHE L1 EVICT error',
        ],
        'APEI_EVENTS': [
            {'APEI Informational Error:': {
                'Error Status': '0x0',
                'Physical Address': '0x72aed744c0',
                'Physical Address Mask': '0x3fffffffffc0',
                'Node': '2',
                'Card': '1',
                'Module': '0',
                'Device': '15',
                'Row': '8165',
                'Column': '184',
                'Memory Error Type': '2',
                'Rank Number': '0',
                'Card Handle': '0xf',
                'Module Handle': '0x1a',
                'Bank Group': '3',
                'Bank Address': '1',
                'Chip Identification': '0',
                'Flags': '0x1',
                'FRU Text': 'P2-DIMMB1 232891B6',
            }},
        ]
    }
    events = OBJ._parse_msgbuf(msgbuf=unique_mca_events + apei_event)
    assert events == expected_result

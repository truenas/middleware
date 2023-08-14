def r20_variants_or_mini(pr, pnr, dmi):
    """If this is an r20 variant then we return the model
    with the TRUENAS- suffix stripped. Otherwise, if this is
    a MINI then we just return the entire string.

    NOTE: this information is burned in by the production team
    into the motherboard (SMBIOS) before we ship the system
    """
    if dmi in ['TRUENAS-R20', 'TRUENAS-R20A', 'TRUENAS-R20B']:
        return pr, True
    elif dmi.startswith(('TRUENAS-MINI', 'FREENAS-MINI')):
        # minis do not have the TRUENAS- prefix removed
        return pnr, True
    else:
        return '', False


def get_enclosure_model_and_controller(key, dmi):
    """This maps the enclosure to the respective platform.
    the 'key' is the concatenated string of t10 vendor and product
    info returned by a standard INQUIRY command to the enclosure
    device.

    NOTE: If the key doesn't exist in this dictionary then we're
    not going to properly map the enclosure.
    """
    pr, pnr = dmi.replace('TRUENAS-', ''), dmi
    try:
        return {
            # M series
            'ECStream_4024Sp': ('M Series', True),
            'ECStream_4024Ss': ('M Series', True),
            'iX_4024Sp': ('M Series', True),
            'iX_4024Ss': ('M Series', True),
            # X series
            'CELESTIC_P3215-O': ('X Series', True),
            'CELESTIC_P3217-B': ('X Series', True),
            # R series (just uses dmi info for model)
            'ECStream_FS1': (pr, True),
            'ECStream_FS2': (pr, True),
            'ECStream_DSS212Sp': (pr, True),
            'ECStream_DSS212Ss': (pr, True),
            'iX_FS1': (pr, True),
            'iX_FS2': (pr, True),
            'iX_DSS212Sp': (pr, True),
            'iX_DSS212Ss': (pr, True),
            # R20
            'iX_TrueNAS R20p': (pr, True),
            'iX_TrueNAS 2012Sp': (pr, True),
            'iX_TrueNAS SMC SC826-P': (pr, True),
            # R20 variants
            'AHCI_SGPIOEnclosure': r20_variants_or_mini(pr, pnr, dmi),
            # R50
            'iX_eDrawer4048S1': (pr, True),
            'iX_eDrawer4048S2': (pr, True),
            # JBODS
            'ECStream_3U16RJ-AC.r3': ('E16', False),
            'Storage_1729': ('E24', False),
            'QUANTA _JB9 SIM': ('E60', False),
            'CELESTIC_X2012': ('ES12', False),
            'ECStream_4024J': ('ES24', False),
            'iX_4024J': ('ES24', False),
            'ECStream_2024Jp': ('ES24F', False),
            'ECStream_2024Js': ('ES24F', False),
            'iX_2024Jp': ('ES24F', False),
            'iX_2024Js': ('ES24F', False),
            'CELESTIC_R0904': ('ES60', False),
            'HGST_H4102-J': ('ES102', False),
            'VikingES_NDS-41022-BB': ('ES102S', False),
        }[key]
    except KeyError:
        return '', False

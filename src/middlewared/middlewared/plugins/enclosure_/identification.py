def get_enclosure_model_and_controller(key, dmi):
    """This maps the enclosure to the respective platform.
    the 'key' is the concatenated string of t10 vendor and product
    info returned by a standard INQUIRY command to the enclosure
    device.
    """
    model = dmi.removeprefix('TRUENAS-').removeprefix('FREENAS-')
    model = model.removesuffix('-HA').removesuffix('-S')
    match key:
        case 'ECStream_4024Sp' | 'ECStream_4024Ss' | 'iX_4024Sp' | 'iX_4024Ss':
            # M series
            return model, True
        case 'CELESTIC_P3215-O' | 'CELESTIC_P3217-B':
            # X series
            return model, True
        case 'BROADCOM_VirtualSES':
            # H series
            if dmi.startswith('TRUENAS-H'):
                return model, True
            else:
                return '', False
        case 'ECStream_FS1' | 'ECStream_FS2' | 'ECStream_DSS212Sp' | 'ECStream_DSS212Ss':
            # R series
            return model, True
        case 'iX_FS1L' | 'iX_FS2' | 'iX_DSS212Sp' | 'iX_DSS212Ss':
            # more R series
            return model, True
        case 'iX_TrueNASR20p' | 'iX_2012Sp' | 'iX_TrueNASSMCSC826-P':
            # R20
            return model, True
        case 'AHCI_SGPIOEnclosure':
            if dmi.startswith((
                'TRUENAS-R20', 'TRUENAS-R20A', 'TRUENAS-R20B',
                'TRUENAS-MINI', 'FREENAS-MINI'
            )):
                # R20 variants or MINIs
                return model, True
            else:
                return '', False
        case 'iX_eDrawer4048S1' | 'iX_eDrawer4048S2':
            # R50
            return model, True

        # JBODS
        case 'ECStream_3U16RJ-AC.r3':
            return 'E16', False
        case 'Storage_1729':
            return 'E24', False
        case 'QUANTA_JB9SIM':
            return 'E60', False
        case 'CELESTIC_X2012':
            return 'ES12', False
        case 'ECStream_4024J' | 'iX_4024J':
            return 'ES24', False
        case 'ECStream_2024Jp' | 'ECStream_2024Js' | 'iX_2024Jp' | 'iX_2024Js':
            return 'ES24F', False
        case 'CELESTIC_R0904-F0001-01':
            return 'ES60', False
        case 'HGST_H4060-J':
            return 'ES60G2', False
        case 'HGST_H4102-J':
            return 'ES102', False
        case 'VikingES_NDS-41022-BB':
            return 'ES102G2', False
        case _:
            return '', False

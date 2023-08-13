def get_slot_info(model):
    """This function returns a dictionary that maps
    drives from their original slots to their mapped slots. This
    is done solely for the purpose of displaying the enclosure
    information to the end-user in a logical way.
    (i.e. /dev/sda is cabled to slot 5 at OS level, so we need
    to map it back to slot 1, etc).

    The keys of the dictionary serve a very particular purpose
    and will be described as follows:
        `any_versions When set to `True`, it means that versions of the
            platform DO NOT MATTER and all versions (there may only be 1)
            ship with the same drive mapping.

        `versions` is a dictionary with many nested keys that
            represent different versions of the same platform.
            Sometimes (not often) we have to make a change to a
            platform because, for example, a particlar part is
            no longer available. We keep the same platform, but
            instead ship with a different piece of hardware.
            Completely transparent to the end-user but, obviously,
            needs to be tracked on our side.

        `versions->[vers_key]` is a dictionary that represents the
            version. So, for example, if we ship an R20 and the
            `any_versions` key is True, then we will access the
            `versions->DEFAULT` key by "default". However, if
            `any_versions` is False, then there should be another
            top-level key that represents the identifier for that
            version on the platform.
            (i.e. {'versions':
                      'DEFAULT': ...
                      '1.0': ...
                      '2.0': ...
                      etc ...
                  }
            )

            NOTE: the version key has to be obtained via SMBIOS
            since we need a value that isn't dynamic and gurantees
            uniqueness. There are exceptions, of course, but this
            is the preferred way of determining the version.

        `versions->[vers_key]->[unique_identifier]` is a top-level
            key that represents a non-changing, guaranteed unique
            identifier for the enclosure that needs to be mapped.
            For example:
            {'versions': {
                'DEFAULT': {
                    'product': {}
                }
            }}
            The `product` key up above represents the top-level key
            that we can use to access the dictionary that is returned
            from `map_enclosures` function. In this example, the
            `product` key represents the "product" string that is returned
            from a standard INQUIRY command sent to the enclosure device.

            It is VERY important that the key placed here is using some
            identifier that is _GUARANTEED_ to be unique for the enclosure
            that you're trying to map. If this is not unique, then the
            entire mapping process will NOT work. It's almost a necessity
            to use a key that is from the hardware (INQUIRY or SMBIOS).
            There is 1 exception to this and that's when we're mapping
            the systems that we sell that utilize the virtual AHCI enclosure
            driver. This enumerates the disks using an `id` that is
            hard-coded in the kernel module which guarantees its uniqueness.


        `versions->[vers_key]->[unique_identifier]->[unique_id_value]` is a
            top-level key that represents the value that is returned by accessing
            the object from the `map_enclosures` function via the unique id
            key that was discussed up above. For example:
            {'versions': {
                'DEFAULT': {
                    'product': {'eDrawer4048S1' : {}}
                }
            }}
            In this example the `eDrawer4048S1` is the value expected to be returned
            from the `product` key from the dictionary returned in the `map_enclosures`
            function. Again, the `product` key is found via an INQUIRY response
            and the `eDrawer4048S1` is the value that is returned from said INQUIRY.

        `versions->[vers_key]->[unique_identifier]->[unique_id_value]->[slot_mapping] is
            a dictionary that is used to map the original drive slots to their mapped
            slots. For example:
            {'versions': {
                'DEFAULT': {
                    'product': {'eDrawer4048S1' : {
                        1: {'orig_slot': 1, 'mapped_slot': 1},
                        5: {'orig_slot': 5, 'mapped_slot': 2},
                    }}
                }
            }}
            The `1` key is the original slot and the dictionary value for that key
            should be self-explanatory. This is essentially where and how the drives
            get mapped.

    We use a complex nested dictionary for a couple reasons.
        1. performance is good when accessing the top-level keys
        2. flexibility is also good since we're able to essentially
            add any type of "key" at any point in the nested object
            to represent a particular change in any of our platforms
            that need it.
        3. necessity because the logic that is required to map all of
            our enclosures is quite complex and this was the best mix
            of performance/maintability.
    """
    if model in ('R50', 'R50B', 'R50BM'):
        # these platforms share same enclosure and mapping
        # but it's important to always map the eDrawer4048S1
        # enclosure device to drives 1 - 24

        # FIXME: R40 does not have a predictable guaranteed unique
        # identifier so we'll map the 1st 24 drives to the
        # enclosure with the smaller logical id and the last
        # 24 drives to the larger logical id
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'product': {
                        'eDrawer4048S1': {
                            1: {'orig_slot': 1, 'mapped_slot': 1},
                            2: {'orig_slot': 2, 'mapped_slot': 2},
                            3: {'orig_slot': 3, 'mapped_slot': 3},
                            4: {'orig_slot': 4, 'mapped_slot': 4},
                            5: {'orig_slot': 5, 'mapped_slot': 5},
                            6: {'orig_slot': 6, 'mapped_slot': 6},
                            7: {'orig_slot': 7, 'mapped_slot': 7},
                            8: {'orig_slot': 8, 'mapped_slot': 8},
                            9: {'orig_slot': 9, 'mapped_slot': 9},
                            10: {'orig_slot': 10, 'mapped_slot': 10},
                            11: {'orig_slot': 11, 'mapped_slot': 11},
                            12: {'orig_slot': 12, 'mapped_slot': 12},
                            13: {'orig_slot': 13, 'mapped_slot': 13},
                            14: {'orig_slot': 14, 'mapped_slot': 14},
                            15: {'orig_slot': 15, 'mapped_slot': 15},
                            16: {'orig_slot': 16, 'mapped_slot': 16},
                            17: {'orig_slot': 17, 'mapped_slot': 17},
                            18: {'orig_slot': 18, 'mapped_slot': 18},
                            19: {'orig_slot': 19, 'mapped_slot': 19},
                            20: {'orig_slot': 20, 'mapped_slot': 20},
                            21: {'orig_slot': 21, 'mapped_slot': 21},
                            22: {'orig_slot': 22, 'mapped_slot': 22},
                            23: {'orig_slot': 23, 'mapped_slot': 23},
                            24: {'orig_slot': 24, 'mapped_slot': 24},
                        },
                        'eDrawer4048S2': {
                            1: {'orig_slot': 1, 'mapped_slot': 25},
                            2: {'orig_slot': 2, 'mapped_slot': 26},
                            3: {'orig_slot': 3, 'mapped_slot': 27},
                            4: {'orig_slot': 4, 'mapped_slot': 28},
                            5: {'orig_slot': 5, 'mapped_slot': 29},
                            6: {'orig_slot': 6, 'mapped_slot': 30},
                            7: {'orig_slot': 7, 'mapped_slot': 31},
                            8: {'orig_slot': 8, 'mapped_slot': 32},
                            9: {'orig_slot': 9, 'mapped_slot': 33},
                            10: {'orig_slot': 10, 'mapped_slot': 34},
                            11: {'orig_slot': 11, 'mapped_slot': 35},
                            12: {'orig_slot': 12, 'mapped_slot': 36},
                            13: {'orig_slot': 13, 'mapped_slot': 37},
                            14: {'orig_slot': 14, 'mapped_slot': 38},
                            15: {'orig_slot': 15, 'mapped_slot': 39},
                            16: {'orig_slot': 16, 'mapped_slot': 40},
                            17: {'orig_slot': 17, 'mapped_slot': 41},
                            18: {'orig_slot': 18, 'mapped_slot': 42},
                            19: {'orig_slot': 19, 'mapped_slot': 43},
                            20: {'orig_slot': 20, 'mapped_slot': 44},
                            21: {'orig_slot': 21, 'mapped_slot': 45},
                            22: {'orig_slot': 22, 'mapped_slot': 46},
                            23: {'orig_slot': 23, 'mapped_slot': 47},
                            24: {'orig_slot': 24, 'mapped_slot': 48},
                        }
                    },
                    'id': {
                        'r50_nvme_enclosure': {
                            1: {'orig_slot': 1, 'mapped_slot': 49},
                            2: {'orig_slot': 1, 'mapped_slot': 50},
                            3: {'orig_slot': 3, 'mapped_slot': 51},
                        },
                        'r50b_nvme_enclosure': {
                            1: {'orig_slot': 1, 'mapped_slot': 49},
                            2: {'orig_slot': 1, 'mapped_slot': 50},
                        },
                        'r50bm_nvme_enclosure': {
                            1: {'orig_slot': 1, 'mapped_slot': 49},
                            2: {'orig_slot': 1, 'mapped_slot': 50},
                            3: {'orig_slot': 3, 'mapped_slot': 51},
                            4: {'orig_slot': 4, 'mapped_slot': 52},
                        },
                    }
                }
            }}
        }
    elif model == 'R10':
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            1: {'orig_slot': 1, 'mapped_slot': 1},
                            5: {'orig_slot': 5, 'mapped_slot': 2},
                            9: {'orig_slot': 9, 'mapped_slot': 3},
                            13: {'orig_slot': 13, 'mapped_slot': 4},
                            2: {'orig_slot': 2, 'mapped_slot': 5},
                            6: {'orig_slot': 6, 'mapped_slot': 6},
                            10: {'orig_slot': 10, 'mapped_slot': 7},
                            14: {'orig_slot': 14, 'mapped_slot': 8},
                            3: {'orig_slot': 3, 'mapped_slot': 9},
                            7: {'orig_slot': 7, 'mapped_slot': 10},
                            11: {'orig_slot': 11, 'mapped_slot': 11},
                            15: {'orig_slot': 15, 'mapped_slot': 12},
                            4: {'orig_slot': 4, 'mapped_slot': 13},
                            8: {'orig_slot': 8, 'mapped_slot': 14},
                            12: {'orig_slot': 12, 'mapped_slot': 15},
                            16: {'orig_slot': 16, 'mapped_slot': 16}
                        }
                    }
                }
            }}
        }
    elif model in ('R20', 'R20B'):
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            3: {'orig_slot': 3, 'mapped_slot': 1},
                            6: {'orig_slot': 6, 'mapped_slot': 2},
                            9: {'orig_slot': 9, 'mapped_slot': 3},
                            12: {'orig_slot': 12, 'mapped_slot': 4},
                            2: {'orig_slot': 2, 'mapped_slot': 5},
                            5: {'orig_slot': 5, 'mapped_slot': 6},
                            8: {'orig_slot': 8, 'mapped_slot': 7},
                            11: {'orig_slot': 11, 'mapped_slot': 8},
                            1: {'orig_slot': 1, 'mapped_slot': 9},
                            4: {'orig_slot': 4, 'mapped_slot': 10},
                            7: {'orig_slot': 7, 'mapped_slot': 11},
                            10: {'orig_slot': 10, 'mapped_slot': 12}
                        }
                    },
                    'id': {
                        '3000000000000001': {
                            1: {'orig_slot': 1, 'mapped_slot': 13},
                            2: {'orig_slot': 2, 'mapped_slot': 14}
                        }
                    }
                }
            }}
        }
    elif model == 'R20A':
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            3: {'orig_slot': 3, 'mapped_slot': 1},
                            6: {'orig_slot': 6, 'mapped_slot': 2},
                            9: {'orig_slot': 9, 'mapped_slot': 3},
                            12: {'orig_slot': 12, 'mapped_slot': 4},
                            2: {'orig_slot': 2, 'mapped_slot': 5},
                            5: {'orig_slot': 5, 'mapped_slot': 6},
                            8: {'orig_slot': 8, 'mapped_slot': 7},
                            11: {'orig_slot': 11, 'mapped_slot': 8},
                            1: {'orig_slot': 1, 'mapped_slot': 9},
                            4: {'orig_slot': 4, 'mapped_slot': 10},
                            7: {'orig_slot': 7, 'mapped_slot': 11},
                            10: {'orig_slot': 10, 'mapped_slot': 12}
                        }
                    },
                    'id': {
                        '3000000000000001': {
                            1: {'orig_slot': 1, 'mapped_slot': 13},
                            2: {'orig_slot': 2, 'mapped_slot': 14}
                        }
                    }
                }
            }}
        }
    elif model == 'MINI-3.0-E':
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            1: {'orig_slot': 1, 'mapped_slot': 1},
                            2: {'orig_slot': 2, 'mapped_slot': 2},
                            3: {'orig_slot': 3, 'mapped_slot': 3},
                            4: {'orig_slot': 4, 'mapped_slot': 4},
                            5: {'orig_slot': 5, 'mapped_slot': 5},
                            6: {'orig_slot': 6, 'mapped_slot': 6}
                        }
                    }
                }
            }}
        }
    elif model == 'MINI-3.0-E+':
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            1: {'orig_slot': 1, 'mapped_slot': 1},
                            2: {'orig_slot': 2, 'mapped_slot': 2},
                            3: {'orig_slot': 3, 'mapped_slot': 3},
                            4: {'orig_slot': 4, 'mapped_slot': 4},
                        },
                        '3000000000000002': {
                            1: {'orig_slot': 1, 'mapped_slot': 5},
                            2: {'orig_slot': 2, 'mapped_slot': 6}

                        }
                    }
                }
            }}
        }
    elif model == 'MINI-3.0-X':
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                # TODO: 1.0 "version" has same mapping?? (CORE is the same)
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            1: {'orig_slot': 1, 'mapped_slot': 1},
                            2: {'orig_slot': 2, 'mapped_slot': 2},
                            3: {'orig_slot': 3, 'mapped_slot': 3},
                            4: {'orig_slot': 4, 'mapped_slot': 4},
                        },
                        '3000000000000002': {
                            1: {'orig_slot': 1, 'mapped_slot': 5},
                            2: {'orig_slot': 2, 'mapped_slot': 6},
                            4: {'orig_slot': 4, 'mapped_slot': 7}

                        }
                    }
                }
            }}
        }
    elif model == 'MINI-3.0-X+':
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            1: {'orig_slot': 1, 'mapped_slot': 1},
                            2: {'orig_slot': 2, 'mapped_slot': 2},
                            3: {'orig_slot': 3, 'mapped_slot': 3},
                            4: {'orig_slot': 4, 'mapped_slot': 4},
                            5: {'orig_slot': 5, 'mapped_slot': 5},
                            6: {'orig_slot': 6, 'mapped_slot': 6},
                            7: {'orig_slot': 7, 'mapped_slot': 7}
                        }
                    }
                }
            }}
        }
    elif model == 'MINI-3.0-XL+':
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000002': {
                            6: {'orig_slot': 6, 'mapped_slot': 1},
                        },
                        '3000000000000001': {
                            1: {'orig_slot': 1, 'mapped_slot': 2},
                            2: {'orig_slot': 2, 'mapped_slot': 3},
                            3: {'orig_slot': 3, 'mapped_slot': 4},
                            4: {'orig_slot': 4, 'mapped_slot': 5},
                            5: {'orig_slot': 5, 'mapped_slot': 6},
                            6: {'orig_slot': 6, 'mapped_slot': 7},
                            7: {'orig_slot': 6, 'mapped_slot': 8},
                            8: {'orig_slot': 6, 'mapped_slot': 9}
                        }
                    }
                }
            }}
        }
    elif model == 'MINI-R':
        return {
            'any_version': True,
            'mapping_info': {'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            1: {'orig_slot': 1, 'mapped_slot': 2},
                            2: {'orig_slot': 2, 'mapped_slot': 3},
                            3: {'orig_slot': 3, 'mapped_slot': 4},
                            4: {'orig_slot': 4, 'mapped_slot': 5},
                            5: {'orig_slot': 5, 'mapped_slot': 6},
                            6: {'orig_slot': 6, 'mapped_slot': 7},
                            7: {'orig_slot': 6, 'mapped_slot': 8}
                        },
                        '3000000000000002': {
                            4: {'orig_slot': 4, 'mapped_slot': 9},
                            5: {'orig_slot': 5, 'mapped_slot': 10},
                            6: {'orig_slot': 6, 'mapped_slot': 11},
                            7: {'orig_slot': 7, 'mapped_slot': 12}
                        }
                    }
                }
            }}
        }
    else:
        return {}


MAPPINGS = {
    """
    The keys represent what was burned
    into SMBIOS from production team
    before the system is shipped to the
    user.

    The only exception to this is the
    keys that have underscores in them
    which are platforms that have nvme
    drives that represent usable disks
    but are not physically present where
    all the other disks are. We still
    need to map them to slots on then
    enclosure.
    """
    'TRUENAS-R10': get_slot_info('R10'),
    'TRUENAS-R20': get_slot_info('R20'),
    'TRUENAS-R20A': get_slot_info('R20A'),
    'TRUENAS-R20B': get_slot_info('R20B'),
    'TRUENAS-R40': get_slot_info('R40'),
    'TRUENAS-R50': get_slot_info('R50'),
    'r50_nvme_enclosure': get_slot_info('R50'),
    'TRUENAS-R50B': get_slot_info('R50B'),
    'r50b_nvme_enclosure': get_slot_info('R50B'),
    'TRUENAS-R50BM': get_slot_info('R50BM'),
    'r50bm_nvme_enclosure': get_slot_info('R50BM'),
    'TRUENAS-MINI-3.0-E': get_slot_info('MINI-3.0-E'),
    'FREENAS-MINI-3.0-E': get_slot_info('MINI-3.0-E'),
    'TRUENAS-MINI-3.0-E+': get_slot_info('MINI-3.0-E+'),
    'FREENAS-MINI-3.0-E+': get_slot_info('MINI-3.0-E+'),
    'TRUENAS-MINI-3.0-X': get_slot_info('MINI-3.0-X'),
    'FREENAS-MINI-3.0-X': get_slot_info('MINI-3.0-X'),
    'TRUENAS-MINI-3.0-X+': get_slot_info('MINI-3.0-X+'),
    'FREENAS-MINI-3.0-X+': get_slot_info('MINI-3.0-X+'),
    'TRUENAS-MINI-3.0-XL+': get_slot_info('MINI-3.0-XL+'),
    'FREENAS-MINI-3.0-XL+': get_slot_info('MINI-3.0-XL+'),
    'TRUENAS-MINI-R': get_slot_info('MINI-R'),
    'FREENAS-MINI-R': get_slot_info('MINI-R')
}

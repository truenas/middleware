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
                        1: {'sysfs_slot': 1, 'mapped_slot': 1},
                        5: {'sysfs_slot': 5, 'mapped_slot': 2},
                    }}
                }
            }}
            The `1` key represents what we get from libsg3.ses.EnclosureDevice().status().
            The values returned from that function are _INDEX_ values from sg3_utils api.
            These are _NOT_ the device slot numbers that the HBA reports. Most of the time,
            the index values map 1 to 1 with the `/sys/class/enclosure/*/slot00/slot` value
            from sysfs. NOTE: sysfs reports the drive slot numbers BY DEFAULT which means
            they have the possibility of NOT mapping to the response we get from the sg3_utils
            api function that we wrote. Of course, if sysfs can't determine the drive slot
            number from the HBA (this happens with Virtual AHCI device) then sysfs will just
            enumerate the `slot` files starting at 0 (mimicking what sg3_utils does).

            For example, a returned response from `EnclosureDevice().status()` looks like this
            >>> pprint(EnclosureDevice('/dev/bsg/0:0:0:0').status())
            {'elements': {
                0: {'descriptor': '<empty>', 'status': [0, 0, 0, 0], 'type': 23},
                1: {'descriptor': '<empty>', 'status': [5, 0, 0, 0], 'type': 23},
                2: {'descriptor': '<empty>', 'status': [5, 0, 0, 0], 'type': 23},
                3: {'descriptor': '<empty>', 'status': [1, 0, 0, 0], 'type': 23},
                4: {'descriptor': '<empty>', 'status': [5, 0, 0, 0], 'type': 23},
            }}

            If we take look at the elements[1] key we might think that the device slot is 1 but
            it's not guaranteed. If we compare what sysfs gives us for slot 1 we see something
            like this:
            root@truenas[~]# cat /sys/class/enclosure/0:0:0:0/9/slot
            root@truenas[~]# 1

            If we compare the sysfs output with the dictionary response, we can see that the directory
            name actually is `9` which represents the drive slot reported by the HBA. This means
            what we get from sg3_utils does not match 1 to 1 with sysfs. So how we determine how to
            "map" the drives to their "original slots" is doing 2 things:

                1. platform team needs to give us a sysfs `slot` mapping (i.e. what `slot` maps to
                    what physical slot in the enclosure) (i.e. `slot` 0 is physical slot 8, etc)
                2. take the `EnclosureDevice().status()` output and map the index values to their
                    respective sysfs `slot` files

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
    if model == 'R40':
        # FIXME: it's impossible to map 0-23 drives to an enclosure
        # while mapping 24-48 drives to an enclosure on this platform.
        # Both expanders in the OS are flashed the same way so we can't
        # determine which is which. Platform team is investigating how
        # they can get this fixed. (ticket: PLAT-172)
        return
        """
        ses_logical_ids = {int(f'0x{i["id"]}', 16): i['id'] for i in enclosures if i['controller']}
        min_id, max_id = min(ses_logical_ids), max(ses_logical_ids)
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'id': {
                        ses_logical_ids[min_id]: {
                            # 1 - 24
                            i: {'sysfs_slot': i, 'mapped_slot': i} for i in range(1, 25)
                        },
                        ses_logical_ids[max_id]: {
                            # 25 - 48
                            i: {'sysfs_slot': i, 'mapped_slot': j} for i, j in zip(range(1, 25), range(25, 49))
                        }
                    }
                }
            }
        }
        """
    elif model in ('R50', 'r50_nvme_enclosure', 'R50B', 'r50b_nvme_enclosure', 'R50BM', 'r50bm_nvme_enclosure'):
        # these platforms share same enclosure and mapping
        # but it's important to always map the eDrawer4048S1
        # enclosure device to drives 1 - 24
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'product': {
                        'eDrawer4048S1': {
                            # 1 - 24
                            i: {'sysfs_slot': i, 'mapped_slot': i} for i in range(1, 25)
                        },
                        'eDrawer4048S2': {
                            # 25 - 48
                            i: {'sysfs_slot': i, 'mapped_slot': j} for i, j in zip(range(1, 25), range(25, 49))
                        }
                    },
                    'id': {
                        'r50_nvme_enclosure': {
                            1: {'sysfs_slot': 1, 'mapped_slot': 49},
                            2: {'sysfs_slot': 2, 'mapped_slot': 50},
                            3: {'sysfs_slot': 3, 'mapped_slot': 51},
                        },
                        'r50b_nvme_enclosure': {
                            1: {'sysfs_slot': 1, 'mapped_slot': 49},
                            2: {'sysfs_slot': 2, 'mapped_slot': 50},
                        },
                        'r50bm_nvme_enclosure': {
                            1: {'sysfs_slot': 1, 'mapped_slot': 49},
                            2: {'sysfs_slot': 2, 'mapped_slot': 50},
                            3: {'sysfs_slot': 3, 'mapped_slot': 51},
                            4: {'sysfs_slot': 4, 'mapped_slot': 52},
                        },
                    }
                }
            }
        }
    elif model == 'R10':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            1: {'sysfs_slot': 0, 'mapped_slot': 1},
                            5: {'sysfs_slot': 4, 'mapped_slot': 2},
                            9: {'sysfs_slot': 5, 'mapped_slot': 3},
                            13: {'sysfs_slot': 12, 'mapped_slot': 4},
                            2: {'sysfs_slot': 1, 'mapped_slot': 5},
                            6: {'sysfs_slot': 5, 'mapped_slot': 6},
                            10: {'sysfs_slot': 9, 'mapped_slot': 7},
                            14: {'sysfs_slot': 13, 'mapped_slot': 8},
                            3: {'sysfs_slot': 2, 'mapped_slot': 9},
                            7: {'sysfs_slot': 6, 'mapped_slot': 10},
                            11: {'sysfs_slot': 10, 'mapped_slot': 11},
                            15: {'sysfs_slot': 14, 'mapped_slot': 12},
                            4: {'sysfs_slot': 3, 'mapped_slot': 13},
                            8: {'sysfs_slot': 7, 'mapped_slot': 14},
                            12: {'sysfs_slot': 11, 'mapped_slot': 15},
                            16: {'sysfs_slot': 15, 'mapped_slot': 16}
                        }
                    }
                }
            }
        }
    elif model in ('R20', 'R20B', '3000000000000001'):
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            3: {'sysfs_slot': 2, 'mapped_slot': 1},
                            6: {'sysfs_slot': 5, 'mapped_slot': 2},
                            9: {'sysfs_slot': 8, 'mapped_slot': 3},
                            12: {'sysfs_slot': 11, 'mapped_slot': 4},
                            2: {'sysfs_slot': 1, 'mapped_slot': 5},
                            5: {'sysfs_slot': 4, 'mapped_slot': 6},
                            8: {'sysfs_slot': 7, 'mapped_slot': 7},
                            11: {'sysfs_slot': 10, 'mapped_slot': 8},
                            1: {'sysfs_slot': 0, 'mapped_slot': 9},
                            4: {'sysfs_slot': 3, 'mapped_slot': 10},
                            7: {'sysfs_slot': 6, 'mapped_slot': 11},
                            10: {'sysfs_slot': 9, 'mapped_slot': 12}
                        }
                    },
                    'id': {
                        '3000000000000001': {
                            1: {'sysfs_slot': 0, 'mapped_slot': 13},
                            2: {'sysfs_slot': 1, 'mapped_slot': 14}
                        }
                    }
                }
            }
        }
    elif model == 'R20A':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            3: {'sysfs_slot': 2, 'mapped_slot': 1},
                            6: {'sysfs_slot': 5, 'mapped_slot': 2},
                            9: {'sysfs_slot': 8, 'mapped_slot': 3},
                            12: {'sysfs_slot': 11, 'mapped_slot': 4},
                            2: {'sysfs_slot': 1, 'mapped_slot': 5},
                            5: {'sysfs_slot': 4, 'mapped_slot': 6},
                            8: {'sysfs_slot': 7, 'mapped_slot': 7},
                            11: {'sysfs_slot': 10, 'mapped_slot': 8},
                            1: {'sysfs_slot': 0, 'mapped_slot': 9},
                            4: {'sysfs_slot': 3, 'mapped_slot': 10},
                            7: {'sysfs_slot': 6, 'mapped_slot': 11},
                            10: {'sysfs_slot': 9, 'mapped_slot': 12}
                        }
                    },
                    'id': {
                        '3000000000000001': {
                            1: {'sysfs_slot': 0, 'mapped_slot': 13},
                            2: {'sysfs_slot': 1, 'mapped_slot': 14}
                        }
                    }
                }
            }
        }
    elif model == 'MINI-3.0-E':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            i: {'sysfs_slot': i - 1, 'mapped_slot': i} for i in range(1, 7)
                        }
                    }
                }
            }
        }
    elif model == 'MINI-3.0-E+':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            i: {'sysfs_slot': i - 1, 'mapped_slot': i} for i in range(1, 5)
                        },
                        '3000000000000002': {
                            1: {'sysfs_slot': 0, 'mapped_slot': 5},
                            2: {'sysfs_slot': 1, 'mapped_slot': 6}
                        }
                    }
                }
            }
        }
    elif model == 'MINI-3.0-X':
        return {
            'any_version': True,
            'versions': {
                # NOTE: 1.0 "version" has same mapping?? (CORE is the same)
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            i: {'sysfs_slot': i - 1, 'mapped_slot': i} for i in range(1, 5)
                        },
                        '3000000000000002': {
                            1: {'sysfs_slot': 0, 'mapped_slot': 5},
                            2: {'sysfs_slot': 1, 'mapped_slot': 6},
                            4: {'sysfs_slot': 5, 'mapped_slot': 7}
                        }
                    }
                }
            }
        }
    elif model == 'MINI-3.0-X+':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            i: {'sysfs_slot': i - 1, 'mapped_slot': i} for i in range(1, 9)
                        }
                    }
                }
            }
        }
    elif model == 'MINI-3.0-XL+':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000002': {
                            6: {'sysfs_slot': 5, 'mapped_slot': 1},
                        },
                        '3000000000000001': {
                            i: {'sysfs_slot': i - 1, 'mapped_slot': i + 1} for i in range(1, 9)
                        }
                    }
                }
            }
        }
    elif model == 'MINI-R':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'id': {
                        '3000000000000001': {
                            i: {'sysfs_slot': i - 1, 'mapped_slot': i} for i in range(1, 9)
                        },
                        '3000000000000002': {
                            4: {'sysfs_slot': 3, 'mapped_slot': 9},
                            5: {'sysfs_slot': 4, 'mapped_slot': 10},
                            6: {'sysfs_slot': 5, 'mapped_slot': 11},
                            7: {'sysfs_slot': 6, 'mapped_slot': 12}
                        }
                    }
                }
            }
        }
    elif model in ('H10', 'H20'):
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            1: {'sysfs_slot': 8, 'mapped_slot': 9},
                            2: {'sysfs_slot': 9, 'mapped_slot': 10},
                            3: {'sysfs_slot': 10, 'mapped_slot': 11},
                            4: {'sysfs_slot': 11, 'mapped_slot': 12},
                            # 5, 6, 7, 8 unused/unsupported
                            9: {'sysfs_slot': 0, 'mapped_slot': 1},
                            10: {'sysfs_slot': 1, 'mapped_slot': 2},
                            11: {'sysfs_slot': 2, 'mapped_slot': 3},
                            12: {'sysfs_slot': 3, 'mapped_slot': 4},
                            13: {'sysfs_slot': 4, 'mapped_slot': 5},
                            14: {'sysfs_slot': 5, 'mapped_slot': 6},
                            15: {'sysfs_slot': 6, 'mapped_slot': 7},
                            16: {'sysfs_slot': 7, 'mapped_slot': 8},
                        },
                    }
                }
            }
        }
    elif model in ('M60', 'm60_nvme_enclosure', 'M50', 'm50_nvme_enclosure', 'M40', 'M30'):
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            # 1 - 24
                            i + 1: {'sysfs_slot': i, 'mapped_slot': i + 1} for i in range(0, 24)
                        },
                    },
                    'id': {
                        'm60_nvme_enclosure': {
                            1: {'sysfs_slot': 1, 'mapped_slot': 25},
                            2: {'sysfs_slot': 2, 'mapped_slot': 26},
                            3: {'sysfs_slot': 3, 'mapped_slot': 27},
                            4: {'sysfs_slot': 4, 'mapped_slot': 28},
                        },
                        'm50_nvme_enclosure': {
                            1: {'sysfs_slot': 1, 'mapped_slot': 25},
                            2: {'sysfs_slot': 2, 'mapped_slot': 26},
                            3: {'sysfs_slot': 3, 'mapped_slot': 27},
                            4: {'sysfs_slot': 4, 'mapped_slot': 28},
                        }
                    }
                }
            }
        }
    elif model in ('X10', 'X20'):
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            i + 1: {'sysfs_slot': i, 'mapped_slot': i + 1} for i in range(0, 12)
                        },
                    }
                }
            }
        }
    # JBODs
    elif model == 'ES12':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            i + 1: {'sysfs_slot': i, 'mapped_slot': i + 1} for i in range(0, 12)
                        },
                    }
                }
            }
        }
    elif model in ('ES24', 'ES24F'):
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            i + 1: {'sysfs_slot': i, 'mapped_slot': i + 1} for i in range(0, 24)
                        },
                    }
                }
            }
        }
    elif model in ('ES60', 'ES60S', 'ES60G2'):
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            i + 1: {'sysfs_slot': i, 'mapped_slot': i + 1} for i in range(0, 60)
                        },
                    }
                }
            }
        }
    elif model == 'ES102':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            i + 1: {'sysfs_slot': i, 'mapped_slot': i + 1} for i in range(0, 102)
                        },
                    }
                }
            }
        }
    elif model == 'ES102G2':
        return {
            'any_version': True,
            'versions': {
                'DEFAULT': {
                    'model': {
                        model: {
                            # drives actually start at index 1 (not 0)
                            i: {'sysfs_slot': i, 'mapped_slot': i} for i in range(0, 103)
                        },
                    }
                }
            }
        }
    else:
        return

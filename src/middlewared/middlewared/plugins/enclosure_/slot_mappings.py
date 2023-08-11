def get_slot_info(model):
    if model in ('R40', 'R50', 'R50B', 'R50BM'):
        # these rseries devices share same enclosure and mapping
        # but it's important to always map the eDrawer4048S1
        # enclosure device to drives 1 - 24
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
    'TRUENAS-R10': get_slot_info('R10'),
    'TRUENAS-R20': get_slot_info('R20'),
    'TRUENAS-R20A': get_slot_info('R20A'),
    'TRUENAS-R20B': get_slot_info('R20B'),
    'TRUENAS-R40': get_slot_info('R40'),
    'TRUENAS-R50': get_slot_info('R50'),
    'TRUENAS-R50B': get_slot_info('R50B'),
    'TRUENAS-R50BM': get_slot_info('R50BM'),
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

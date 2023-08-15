import pytest

from middlewared.plugins.enclosure_ import slot_mappings


@pytest.mark.parametrize('data', [
    ('R50', {
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
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                        3: {'orig_slot': 3, 'mapped_slot': 51},
                    },
                    'r50b_nvme_enclosure': {
                        1: {'orig_slot': 1, 'mapped_slot': 49},
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                    },
                    'r50bm_nvme_enclosure': {
                        1: {'orig_slot': 1, 'mapped_slot': 49},
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                        3: {'orig_slot': 3, 'mapped_slot': 51},
                        4: {'orig_slot': 4, 'mapped_slot': 52},
                    }
                }
            }
        }}
    }),
    ('R50B', {
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
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                        3: {'orig_slot': 3, 'mapped_slot': 51},
                    },
                    'r50b_nvme_enclosure': {
                        1: {'orig_slot': 1, 'mapped_slot': 49},
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                    },
                    'r50bm_nvme_enclosure': {
                        1: {'orig_slot': 1, 'mapped_slot': 49},
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                        3: {'orig_slot': 3, 'mapped_slot': 51},
                        4: {'orig_slot': 4, 'mapped_slot': 52},
                    }
                }
            }
        }}
    }),
    ('R50BM', {
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
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                        3: {'orig_slot': 3, 'mapped_slot': 51},
                    },
                    'r50b_nvme_enclosure': {
                        1: {'orig_slot': 1, 'mapped_slot': 49},
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                    },
                    'r50bm_nvme_enclosure': {
                        1: {'orig_slot': 1, 'mapped_slot': 49},
                        2: {'orig_slot': 2, 'mapped_slot': 50},
                        3: {'orig_slot': 3, 'mapped_slot': 51},
                        4: {'orig_slot': 4, 'mapped_slot': 52},
                    }
                }
            }
        }}
    }),
    ('R10', {
        'any_version': True,
        'mapping_info': {'versions': {
            'DEFAULT': {
                'model': {
                    'R10': {
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
    }),
    ('R20', {
        'any_version': True,
        'mapping_info': {'versions': {
            'DEFAULT': {
                'model': {
                    'R20': {
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
    }),
    ('R20B', {
        'any_version': True,
        'mapping_info': {'versions': {
            'DEFAULT': {
                'model': {
                    'R20B': {
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
    }),
    ('R20A', {
        'any_version': True,
        'mapping_info': {'versions': {
            'DEFAULT': {
                'model': {
                    'R20A': {
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
    }),
    ('MINI-3.0-E', {
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
    }),
    ('MINI-3.0-E+', {
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
    }),
    ('MINI-3.0-X', {
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
    }),
    ('MINI-3.0-X+', {
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
    }),
    ('MINI-3.0-XL+', {
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
    }),
    ('MINI-R', {
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
    }),
    ('BAD-MODEL', {})
])
def test_slot_mappings(data):
    model, expected_result = data
    assert slot_mappings.get_slot_info(model) == expected_result

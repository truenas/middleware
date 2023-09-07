import pytest

from middlewared.plugins.enclosure_ import slot_mappings


@pytest.mark.parametrize('data', [
    ('R50', {
        'any_version': True,
        'versions': {
            'DEFAULT': {
                'product': {
                    'eDrawer4048S1': {
                        i: {'orig_slot': i, 'mapped_slot': i} for i in range(1, 25)
                    },
                    'eDrawer4048S2': {
                        i: {'orig_slot': i, 'mapped_slot': j} for i, j in zip(range(1, 25), range(25, 49))
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
        }
    }),
    ('R50B', {
        'any_version': True,
        'versions': {
            'DEFAULT': {
                'product': {
                    'eDrawer4048S1': {
                        i: {'orig_slot': i, 'mapped_slot': i} for i in range(1, 25)
                    },
                    'eDrawer4048S2': {
                        i: {'orig_slot': i, 'mapped_slot': j} for i, j in zip(range(1, 25), range(25, 49))
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
        }
    }),
    ('R50BM', {
        'any_version': True,
        'versions': {
            'DEFAULT': {
                'product': {
                    'eDrawer4048S1': {
                        i: {'orig_slot': i, 'mapped_slot': i} for i in range(1, 25)
                    },
                    'eDrawer4048S2': {
                        i: {'orig_slot': i, 'mapped_slot': j} for i, j in zip(range(1, 25), range(25, 49))
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
        }
    }),
    ('R10', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('R20', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('R20B', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('R20A', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('MINI-3.0-E', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('MINI-3.0-E+', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('MINI-3.0-X', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('MINI-3.0-X+', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('MINI-3.0-XL+', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('MINI-R', {
        'any_version': True,
        'versions': {
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
        }
    }),
    ('BAD-MODEL', None)
])
def test_slot_mappings(data):
    model, expected_result = data
    assert slot_mappings.get_slot_info(model) == expected_result

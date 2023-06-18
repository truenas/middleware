def convert_unit(unit: str) -> int:
    return {
        'HOUR': 60,
        'DAY': 60 * 24,
        'WEEK': 60 * 24 * 7,
        'MONTH': 60 * 24 * 30,
        'YEAR': 60 * 24 * 365,
    }[unit]

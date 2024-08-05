import re


def change_case(value: str) -> str:
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', value)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def convert_case_for_dict_or_list(data: dict | list) -> dict | list:
    if isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            new_key = change_case(key)
            if isinstance(value, dict):
                new_value = convert_case_for_dict_or_list(value)
            elif isinstance(value, list):
                new_value = [convert_case_for_dict_or_list(item) if isinstance(item, dict) else item for item in value]
            else:
                new_value = value
            new_data[new_key] = new_value
        return new_data
    elif isinstance(data, list):
        return [convert_case_for_dict_or_list(item) for item in data]
    else:
        return data

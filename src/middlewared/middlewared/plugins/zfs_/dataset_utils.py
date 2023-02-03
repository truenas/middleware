from copy import deepcopy


def flatten_datasets(datasets):
    return sum([[deepcopy(ds)] + flatten_datasets(ds.get('children') or []) for ds in datasets], [])

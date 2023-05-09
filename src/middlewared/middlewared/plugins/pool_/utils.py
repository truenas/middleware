from pathlib import Path


def get_dataset_parents(dataset: str) -> list:
    return [parent.as_posix() for parent in Path(dataset).parents][:-1]

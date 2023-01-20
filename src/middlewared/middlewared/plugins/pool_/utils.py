import os


def dataset_mountpoint(dataset):
    if dataset['mountpoint'] == 'legacy':
        return None

    return dataset['mountpoint'] or os.path.join('/mnt', dataset['name'])

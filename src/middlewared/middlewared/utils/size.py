import humanfriendly

MB = 1048576


def format_size(size):
    return humanfriendly.format_size(size, binary=True)

import humanfriendly


def format_size(size):
    return humanfriendly.format_size(size, binary=True)

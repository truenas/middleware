import os


def get_middlewared_dir():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.pardir))

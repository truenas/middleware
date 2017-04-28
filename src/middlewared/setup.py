import os
try:
    import fastentrypoints
except ImportError:
    import sys
    print("fastentrypoints module not found. entry points will be slower.", file=sys.stderr)
from setuptools import setup


install_requires = [
    'ws4py',
    'python-dateutil',
    'falcon',
    'markdown',
    'Flask',
    'setproctitle',
    'psutil',
]


def get_etc_files(*args, **kwargs):
    """
    Recursive get dirs from middlewared/etc_files/.
    This is required for the etc plugin.
    """
    base_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'middlewared',
        'etc_files',
    )
    for root, dirs, files in os.walk(base_path):
        if base_path == root:
            yield 'etc_files/*'
        else:
            entry = root.replace(base_path, 'etc_files')
            yield f'{entry}/*'


setup(
    name='middlewared',
    description='FreeNAS Middleware Daemon',
    packages=[
        'middlewared',
        'middlewared.client',
        'middlewared.plugins',
        'middlewared.apidocs',
    ],
    package_data={
        'middlewared.apidocs': [
            'templates/websocket/*',
            'templates/*.*',
        ],
        'middlewared': get_etc_files(),
    },
    include_package_data=True,
    license='BSD',
    platforms='any',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'middlewared = middlewared.main:main',
            'midclt = middlewared.client.client:main',
        ],
    },
)

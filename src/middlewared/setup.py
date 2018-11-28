import os
try:
    import fastentrypoints
except ImportError:
    import sys
    print("fastentrypoints module not found. entry points will be slower.", file=sys.stderr)
from setuptools import find_packages, setup


install_requires = [
    'ws4py',
    'python-dateutil',
    'aiohttp_wsgi',
    'markdown',
    'Flask',
    'setproctitle',
    'psutil',
]


def get_assets(name):
    """
    Recursive get dirs from middlewared/{name}
    """
    base_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'middlewared',
    )
    result = []
    for root, dirs, files in os.walk(os.path.join(base_path, name)):
        result.append(f'{os.path.relpath(root, base_path)}/*')
    return result


setup(
    name='middlewared',
    description='FreeNAS Middleware Daemon',
    packages=find_packages(),
    package_data={
        'middlewared.apidocs': [
            'templates/websocket/*',
            'templates/*.*',
        ],
        'middlewared': get_assets('assets') + get_assets('etc_files'),
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
            'midgdb = middlewared.scripts.gdb:main',
            'sedhelper = middlewared.scripts.sedhelper:main',
        ],
    },
)

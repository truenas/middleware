import os
from setuptools import find_packages, setup


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
        result.extend([f'{os.path.relpath(root, base_path)}/*'] + [
            os.path.join(os.path.relpath(root, base_path), file)
            for file in filter(lambda f: f == '.gitkeep', files)
        ])
    return result


setup(
    name='middlewared',
    description='TrueNAS Middleware Daemon',
    packages=find_packages(),
    package_data={
        'middlewared': (
            get_assets('alembic') +
            ['alembic.ini'] +
            get_assets('assets') +
            get_assets('etc_files') +
            get_assets('migration')
        ),
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
    entry_points={
        'console_scripts': [
            'configure_fips = middlewared.scripts.configure_fips:main',
            'ha_panic = middlewared.scripts.ha_panic:main',
            'setup_cgroups = middlewared.scripts.setup_cgroups:main',
            'middlewared = middlewared.main:main',
            'midgdb = middlewared.scripts.gdb:main',
            'sedhelper = middlewared.scripts.sedhelper:main',
            'wait_to_hang_and_dump_core = middlewared.scripts.wait_to_hang_and_dump_core:main',
            'wait_on_disks = middlewared.scripts.wait_on_disks:main',
            'start_vendor_service = middlewared.scripts.vendor_service:main',
        ],
    },
)

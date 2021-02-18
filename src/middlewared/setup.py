import os
try:
    import fastentrypoints
except ImportError:
    import sys
    print("fastentrypoints module not found. entry points will be slower.", file=sys.stderr)
from setuptools import find_packages, setup
from setuptools.command.install import install

from babel.messages import frontend as babel


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


class InstallWithBabel(install):
    def run(self):
        compiler = babel.compile_catalog(self.distribution)
        option_dict = self.distribution.get_option_dict('compile_catalog')
        compiler.domain = [option_dict['domain'][1]]
        compiler.directory = option_dict['directory'][1]
        compiler.run()
        super().run()


setup(
    name='middlewared',
    description='TrueNAS Middleware Daemon',
    packages=find_packages(),
    package_data={
        'middlewared.apidocs': [
            'templates/websocket/*',
            'templates/*.*',
        ],
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
            'hadetect = middlewared.scripts.hadetect:main',
            'middlewared = middlewared.main:main',
            'midclt = middlewared.client.client:main',
            'midgdb = middlewared.scripts.gdb:main',
            'sedhelper = middlewared.scripts.sedhelper:main',
        ],
    },
    cmdclass={
        'install': InstallWithBabel,

        'compile_catalog': babel.compile_catalog,
        'extract_messages': babel.extract_messages,
        'init_catalog': babel.init_catalog,
        'update_catalog': babel.update_catalog,
    },
)

from setuptools import setup


install_requires = [
    'ws4py',
]

setup(
    name='middlewared.client',
    description='TrueNAS Middleware Daemon Client',
    packages=[
        'middlewared.client',
    ],
    package_data={},
    include_package_data=True,
    license='BSD',
    platforms='any',
    namespace_packages=[str('middlewared')],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'midclt = middlewared.client.client:main',
        ],
    },
)

from setuptools import setup


install_requires = [
    'ws4py<0.4.3',
]

setup(
    name='middlewared',
    description='TrueNAS Middleware Daemon Integration Test Facilities',
    packages=[
        'middlewared.client',
        'middlewared.test.integration.utils',
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
        'Programming Language :: Python :: 3',
    ],
    install_requires=install_requires,
)

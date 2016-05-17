from setuptools import setup


install_requires = [
    'ws4py',
]

setup(
    name='freenas.client',
    description='FreeNAS RPC client library',
    packages=['freenas', 'freenas.client'],
    namespace_packages=[str('freenas')],
    license='BSD',
    platforms='any',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
    install_requires=install_requires,
)

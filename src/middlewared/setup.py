from setuptools import setup


install_requires = [
    'ws4py',
    'gevent',
    'gevent-websocket',
    'Flask',
]

setup(
    name='middlewared',
    description='FreeNAS Middleware Daemon ',
    packages=[
        'middlewared',
        'middlewared.client',
        'middlewared.plugins'],
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
    entry_points={
        'console_scripts': [
            'middlewared = middlewared.main:main',
            'midclt = middlewared.client.client:main',
        ],
    },
)

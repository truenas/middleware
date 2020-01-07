from setuptools import find_packages, setup


setup(
    name='fenced',
    description='TrueNAS Fence Daemon',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    install_requires=[],
    entry_points={
        'console_scripts': [
            'fenced = fenced.main:main',
        ],
    },
)

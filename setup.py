from setuptools import setup

import toml

with open("README.rst") as readme_file:
    readme_string = readme_file.read()

setup(
    name="toml",
    version=toml.__version__,
    description="Python Library for Tom's Obvious, Minimal Language",
    author="William Pearson",
    author_email="uiri@xqz.ca",
    url="https://github.com/uiri/toml",
    packages=['toml'],
    license="MIT",
    long_description=readme_string,
    python_requires=">=3.7",
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ]
)

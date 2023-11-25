
from setuptools import setup

setup(
    name='lemmybot',
    version='0.1',
    description='Homebrew lemmy api wrapper',
    author='Alex Cannan',
    author_email='alexfcannan@gmail.com',
    packages=['lemmybot'],
    install_requires=[
        "aiohttp",
        "pydantic",
    ],
)

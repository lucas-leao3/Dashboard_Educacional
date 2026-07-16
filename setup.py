from setuptools import setup, find_packages

setup(
    name="Dashboard_educacional",
    version="0.1",
    packages=find_packages(), install_requires=['cryptography', 'fastapi', 'SQLAlchemy'],
)
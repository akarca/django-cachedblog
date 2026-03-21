from setuptools import setup, find_packages

setup(
    name="django-cachedblog",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "Django>=4.2",
    ],
    description="A Django app that serves blog posts entirely from cache, fed by an external CMS via API.",
    author="Serdar Akarca",
    license="MIT",
    classifiers=[
        "Framework :: Django",
        "Programming Language :: Python :: 3",
    ],
)

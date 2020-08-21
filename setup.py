"""
pwt.jinja2js is an extension to the Jinja2 template engine that compiles
valid Jinja2 templates containing macros to JavaScript. The JavaScript output
can be included via script tags or can be added to the applications JavaScript.
"""
from setuptools import find_packages, setup

setup(
    name = "jinja2js",
    version = "0.7.5",

    author = "William Kral, Michael Kerrin",
    author_email = "william.kral@gmail.com, michael.kerrin@gmail.com",
    license = "BSD",
    description = __doc__,
    long_description = open("README.md").read(),
    url = "https://github.com/wkral/jinja2js",

    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        # "Programming Language :: Python :: 3",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Markup :: HTML"
    ],

    packages = find_packages(),

    install_requires = ["Jinja2"],

    include_package_data = True,
    zip_safe = False,
    )

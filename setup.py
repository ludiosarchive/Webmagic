#!/usr/bin/env python

from distutils.core import setup

import webmagic

setup(
	name='Webmagic',
	version=webmagic.__version__,
	description="A collection of Twisted and twisted.web-related utilities.",
	url="https://github.com/ludios/Webmagic",
	author="Ivan Kozik",
	author_email="ivan@ludios.org",
	classifiers=[
		'Programming Language :: Python :: 2',
		'Development Status :: 3 - Alpha',
		'Operating System :: OS Independent',
		'Intended Audience :: Developers',
		'License :: OSI Approved :: MIT License',
	],
	packages=['webmagic', 'webmagic.test'],
)

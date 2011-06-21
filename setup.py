#!/usr/bin/env python

from distutils.core import setup

import webmagic

setup(
	name='Webmagic',
	version=webmagic.__version__,
	description=("twisted.web-related utilities involving cookies, "
		"caching headers, cachebreakers, /page -> /page/ "
		"redirection, and more"),
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
	install_requires=[
		 'Twisted >= 8.2.0'
		,'zope.interface'
	],
)

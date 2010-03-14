#!/usr/bin/env python

from distutils.core import setup

import webmagic

setup(
	name='Webmagic',
	version=webmagic.__version__,
	description="Web-related things",
	packages=['webmagic', 'webmagic.test'],
)

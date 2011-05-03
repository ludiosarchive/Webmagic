Webmagic overview
=================

Webmagic is a collection of Twisted and twisted.web-related utilities.


Requirements
============

*	zope.interface

*	Twisted

*	Mypy


Installation
============

`python setup.py install`

This installs the module `webmagic`.


Running the tests
=================

Install Twisted, then run `trial webmagic`


Wishlist
========

*	Document all modules in README.md

*	In `webmagic.cssfixer`, use cssutils instead of a regexp to modify the CSS.


Code style notes
================

This package mostly follows the Divmod Coding Standard
<http://replay.web.archive.org/http://divmod.org/trac/wiki/CodingStandard> with a few exceptions:

*	Use hard tabs for indentation.

*	Use hard tabs only at the beginning of a line.

*	Prefer to have lines <= 80 characters, but always less than 100.

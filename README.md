Webmagic overview
=================

Webmagic is a collection of twisted.web-related utilities involving cookies,
caching headers, cachebreakers, /page -> /page/ redirection, and more.

[TODO: describe everything]


Requirements
============

*	zope.interface

*	Twisted


Installation
============

`python setup.py install`

This installs the module `webmagic`.


Running the tests
=================

Install Twisted, then run `trial webmagic`


Wishlist
========

*	In `webmagic.cssfixer`, use cssutils instead of a regexp to modify the CSS.


Code style notes
================

This package mostly follows the Divmod Coding Standard
<http://replay.web.archive.org/http://divmod.org/trac/wiki/CodingStandard> with a few exceptions:

*	Use hard tabs for indentation.

*	Use hard tabs only at the beginning of a line.

*	Prefer to have lines <= 80 characters, but always less than 100.

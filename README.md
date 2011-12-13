Webmagic overview
=================

Webmagic is a collection of twisted.web-related utilities involving cookies,
caching headers, cachebreakers, /page -> /page/ redirection, and more.

[TODO: describe everything]


Requirements
============

*	zope.interface

*	Twisted >= 8.2.0


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


Contributing
============

Patches and pull requests are welcome.

This coding standard applies: http://ludios.org/coding-standard/

from __future__ import with_statement

import base64

from twisted.trial import unittest

from twisted.python.filepath import FilePath
from twisted.internet.task import Clock
from twisted.web.test import _util
from twisted.web import http, server, resource

from mypy.filecache import FileCache

from webmagic.fakes import DummyChannel, DummyRequest
from webmagic.untwist import (
	CookieInstaller, BetterResource, RedirectingResource, HelpfulNoResource,
	BetterFile,
)


class CookieInstallerTests(unittest.TestCase):

	def setUp(self):
		self._reset()


	def _reset(self):
		self.c = CookieInstaller(secureRandom=lambda nbytes: 'x'*nbytes) # not very random at all
		self.request = http.Request(DummyChannel(), None)


	def test_installsCookieOnCookielessRequest(self):
		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual(
			['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/' % base64.b64encode('x' * 16)],
			self.request.cookies)


	def test_installsSecureCookieOnCookielessRequestHTTPS(self):
		self.request.isSecure = lambda: True
		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual(
			['_s=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/; Secure' % base64.b64encode('x' * 16)],
			self.request.cookies)


	def test_readsAlreadyInstalledCookie(self):
		"""
		Cookie must be very valid for it to be read.
		"""
		self.request.received_cookies['__'] = base64.b64encode('x' * 16)
		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual([], self.request.cookies)


	def test_invalidCookiesIgnored(self):
		invalids = [
			"",
			"\x00",
			base64.b64encode('z' * 15),
			base64.b64encode('z' * 17),
			base64.b64encode('z' * 16).rstrip("="), # TODO: maybe support padding-free base64 in future
			base64.b64encode('z' * 16) + "\x00",
			base64.b64encode('z' * 16) + ";",
			base64.b64encode('z' * 16) + "=",
		]
		for invalid in invalids:
			self._reset()
			self.request.received_cookies['__'] = invalid
			sess = self.c.getSet(self.request)
			self.assertEqual('x' * 16, sess)
			self.assertEqual(
				['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/' % base64.b64encode('x' * 16)],
				self.request.cookies)


	def test_installsCookieWithCustomDomain(self):
		del self.c
		class MyCookieInstaller(CookieInstaller):
			__slots__ = ()
			domain = ".customdomain.com"
		self.c = MyCookieInstaller(secureRandom=lambda nbytes: 'x'*nbytes) # not very random at all

		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual(
			['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Domain=.customdomain.com; Path=/' % base64.b64encode('x' * 16)],
			self.request.cookies)



class Leaf(BetterResource):
	isLeaf = True
	def render_GET(self, request):
		return 'At ' + str(request.URLPath())


class NonLeaf(BetterResource):
	pass



class NonLeafWithChildChild(BetterResource):
	def __init__(self):
		BetterResource.__init__(self)
		child = Leaf()
		self.putChild('child', child)



class NonLeafWithIndexChild(BetterResource):
	def __init__(self):
		BetterResource.__init__(self)
		index = Leaf()
		self.putChild('', index)



class NonLeafWithNonLeafIndexChild(BetterResource):
	def __init__(self):
		BetterResource.__init__(self)
		index = NonLeafWithIndexChild()
		self.putChild('', index)



class LeafPlainResource(resource.Resource):
	isLeaf = True
	def __init__(self):
		resource.Resource.__init__(self)



class NonLeafPlainResource(resource.Resource):
	def __init__(self):
		resource.Resource.__init__(self)



class BetterResourceTests(unittest.TestCase):

	def test_rootURLNotRedirectedWithLeafRoot(self):
		req = DummyRequest([''])
		req.uri = '/'

		r = Leaf()
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, Leaf), res)


	def test_rootURLNotRedirectedWithNonLeafRoot(self):
		req = DummyRequest(['']) # the '' is necessary for this test, not for the above
		req.uri = '/'

		r = NonLeafWithIndexChild()
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, Leaf), res)


	def test_normalRequestNotRedirected(self):
		req = DummyRequest(['hello', ''])
		req.uri = '/hello/'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, Leaf), res)


	def test_redirectedToPathPlusSlash1(self): # For leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, RedirectingResource), res)
		self.assertEqual("/hello/", res._location)


	def test_redirectedToPathPlusSlash2(self): # For non-leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafWithIndexChild()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, RedirectingResource), res)
		self.assertEqual("/hello/", res._location)


	def test_redirectedToPathPlusSlash3(self): # For non-leaf -> non-leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafWithNonLeafIndexChild()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, RedirectingResource), res)
		self.assertEqual("/hello/", res._location)


	def test_normalRequestToNonLeafNonLeafNotRedirected(self):
		req = DummyRequest(['hello', '', '']) # ugh. need to do integration testing and send real requests
		req.uri = '/hello/'

		r = NonLeaf()
		hello = NonLeafWithNonLeafIndexChild()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, Leaf), res)


	def test_notRedirectedBecauseResourceIsNotBetter1(self): # For leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = LeafPlainResource()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, LeafPlainResource), res)


	def test_notRedirectedBecauseResourceIsNotBetter2(self): # For non-leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafPlainResource()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, NonLeafPlainResource), res)


	def test_404forStrangeResourceBecauseNoIndex(self):
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafWithChildChild()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, HelpfulNoResource), res)

		# Sanity check that child is accessible
		req2 = DummyRequest(['hello', 'child'])
		req2.uri = '/hello/child'
		res2 = site.getResourceFor(req2)
		self.assertTrue(isinstance(res2, RedirectingResource), res2)
		self.assertEqual("/hello/child/", res2._location)


	def test_404forBadPath(self):
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		nothello = Leaf()
		r.putChild('nothello', nothello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, HelpfulNoResource), res)


	def test_404urlWithCrud(self):
		req = DummyRequest(['hello', 'there'])
		req.uri = '/hello/there'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, HelpfulNoResource), res)


	def test_404urlWithSlashCrud(self):
		req = DummyRequest(['hello', '', '', ''])
		req.uri = '/hello///'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, HelpfulNoResource), res)


	# Right now, the behavior is to 404 if there are any extra slashes,
	# except for the root Resource, which strange accepts 1 extra slash.

#	def test_redirectWhenOneExtraSlash(self):
#		req = DummyRequest(['hello', '', ''])
#		req.uri = '/hello//'
#
#		r = NonLeaf()
#		hello = Leaf()
#		r.putChild('hello', hello)
#		site = server.Site(r, clock=Clock())
#		res = site.getResourceFor(req)
#		self.assertTrue(isinstance(res, RedirectingResource), res)
#		self.assertEqual("/hello/", res._location)
#
#
#	def test_rootURLRedirectedOneExtraSlashWithLeafRoot(self):
#		req = DummyRequest(['', ''])
#		req.uri = '//'
#
#		r = Leaf()
#		site = server.Site(r, clock=Clock())
#		res = site.getResourceFor(req)
#		self.assertTrue(isinstance(res, RedirectingResource), res)
#		self.assertEqual("/", res._location)
#
#
#	def test_rootURLNotRedirectedOneExtraSlashWithNonLeafRoot(self):
#		req = DummyRequest(['', ''])
#		req.uri = '//'
#
#		r = NonLeafWithIndexChild()
#		site = server.Site(r, clock=Clock())
#		res = site.getResourceFor(req)
#		self.assertTrue(isinstance(res, RedirectingResource), res)
#		self.assertEqual("/", res._location)



class BetterFileTests(unittest.TestCase):

	def test_rewriteCss(self):
		clock = Clock()
		fc = FileCache(lambda: clock.rightNow, 1)
		temp = FilePath(self.mktemp() + '.css')
		with temp.open('wb') as f:
			f.write("p { color: red; }\n")

		# BetterFile(temp.path) would not work because the processing happens
		# in getChild.  So, create a BetterFile for the .css file's parent dir.
		bf = BetterFile(temp.parent().path, fileCache=fc, rewriteCss=True)
		basename = temp.basename()
		request = DummyRequest([basename])
		child = resource.getChildForRequest(bf, request)
		d = _util._render(child, request)
		def _assert(_):
			self.assertEqual("""\
/* Processed by CSSResource */
p { color: red; }
""", ''.join(request.written))
		d.addCallback(_assert)
		return d


	def test_rewriteCssButNoFileCache(self):
		self.assertRaises(
			NotImplementedError,
			lambda: BetterFile('nonexistent', rewriteCss=True))

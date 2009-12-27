import base64

from twisted.trial import unittest

from twisted.internet.task import Clock
from twisted.web.test.test_web import DummyChannel, DummyRequest
from twisted.web import http, server


from webmagic.untwist import (
	CookieInstaller, BetterResource, RedirectingResource, HelpfulNoResource,
)


class CookieInstallerTests(unittest.TestCase):

	def setUp(self):
		self._reset()


	def _reset(self):
		self.c = CookieInstaller(secureRandom=lambda nbytes: 'x'*nbytes) # not very random at all
		self.request = http.Request(DummyChannel(), None)


	def test_installsCookieOnCookielessRequest(self):
		sess = self.c.getSet(self.request)
		self.aE('x' * 16, sess)
		self.aE(
			['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/' % base64.b64encode('x' * 16)],
			self.request.cookies)


	def test_installsSecureCookieOnCookielessRequestHTTPS(self):
		self.request.isSecure = lambda: True
		sess = self.c.getSet(self.request)
		self.aE('x' * 16, sess)
		self.aE(
			['_s=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/; Secure' % base64.b64encode('x' * 16)],
			self.request.cookies)


	def test_readsAlreadyInstalledCookie(self):
		"""
		Cookie must be very valid for it to be read.
		"""
		self.request.received_cookies['__'] = base64.b64encode('x' * 16)
		sess = self.c.getSet(self.request)
		self.aE('x' * 16, sess)
		self.aE([], self.request.cookies)


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
			self.aE('x' * 16, sess)
			self.aE(
				['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/' % base64.b64encode('x' * 16)],
				self.request.cookies)


	def test_installsCookieWithCustomDomain(self):
		self.c.domain = ".customdomain.com"
		sess = self.c.getSet(self.request)
		self.aE('x' * 16, sess)
		self.aE(
			['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Domain=.customdomain.com; Path=/' % base64.b64encode('x' * 16)],
			self.request.cookies)



class Leaf(BetterResource):
	isLeaf = True
	def render_GET(self, request):
		return 'At ' + str(request.URLPath())


class NonLeaf(BetterResource):
	pass



class NonLeafWithChildChild(BetterResource):
	"""Notice how this is not a leaf, and has no render methods."""
	def __init__(self):
		BetterResource.__init__(self)
		child = Leaf()
		self.putChild('child', child)



class NonLeafWithIndexChild(BetterResource):
	"""Notice how this is not a leaf, and has no render methods."""
	def __init__(self):
		BetterResource.__init__(self)
		index = Leaf()
		self.putChild('', index)



class BetterResourceTests(unittest.TestCase):

	def test_rootURLNotRedirectedWithLeafRoot(self):
		req = DummyRequest([''])
		req.uri = '/'

		r = Leaf()
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, Leaf), res)


	def test_rootURLNotRedirectedWithNonLeafRoot(self):
		req = DummyRequest(['']) # the '' is necessary for this test, not for the above
		req.uri = '/'

		r = NonLeafWithIndexChild()
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, Leaf), res)


	def test_normalRequestNotRedirected(self):
		req = DummyRequest(['hello', ''])
		req.uri = '/hello/'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, Leaf), res)


	def test_redirectedToPathPlusSlash(self):
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, RedirectingResource), res)
		self.aE("/hello/", res._location)


	def test_redirectedToPathPlusSlashForNonLeafResource(self):
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafWithIndexChild()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, RedirectingResource), res)
		self.aE("/hello/", res._location)


	def test_404forStrangeResourceBecauseNoIndex(self):
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafWithChildChild()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, HelpfulNoResource), res)

		# Sanity check that child is accessible
		req2 = DummyRequest(['hello', 'child'])
		req2.uri = '/hello/child'
		res2 = site.getResourceFor(req2)
		self.assert_(isinstance(res2, RedirectingResource), res2)
		self.aE("/hello/child/", res2._location)


	def test_404forBadPath(self):
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		nothello = Leaf()
		r.putChild('nothello', nothello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, HelpfulNoResource), res)


	def test_404urlWithCrud(self):
		req = DummyRequest(['hello', 'there'])
		req.uri = '/hello/there'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, HelpfulNoResource), res)


	def test_404urlWithSlashCrud(self):
		req = DummyRequest(['hello', '', '', ''])
		req.uri = '/hello///'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = server.Site(r, clock=Clock())
		res = site.getResourceFor(req)
		self.assert_(isinstance(res, HelpfulNoResource), res)


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
#		self.assert_(isinstance(res, RedirectingResource), res)
#		self.aE("/hello/", res._location)
#
#
#	def test_rootURLRedirectedOneExtraSlashWithLeafRoot(self):
#		req = DummyRequest(['', ''])
#		req.uri = '//'
#
#		r = Leaf()
#		site = server.Site(r, clock=Clock())
#		res = site.getResourceFor(req)
#		self.assert_(isinstance(res, RedirectingResource), res)
#		self.aE("/", res._location)
#
#
#	def test_rootURLNotRedirectedOneExtraSlashWithNonLeafRoot(self):
#		req = DummyRequest(['', ''])
#		req.uri = '//'
#
#		r = NonLeafWithIndexChild()
#		site = server.Site(r, clock=Clock())
#		res = site.getResourceFor(req)
#		self.assert_(isinstance(res, RedirectingResource), res)
#		self.aE("/", res._location)



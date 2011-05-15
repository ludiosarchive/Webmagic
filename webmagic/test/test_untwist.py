from __future__ import with_statement

import re
import base64
import hashlib

from twisted.trial import unittest

from twisted.python.filepath import FilePath
from twisted.internet.task import Clock
from twisted.web.test import _util
from twisted.web import http, server, resource

from webmagic.filecache import FileCache
from webmagic.fakes import DummyChannel, DummyRequest
from webmagic.untwist import (
	CookieInstaller, BetterResource, RedirectingResource, HelpfulNoResource,
	_CSSCacheEntry, BetterFile, ResponseCacheOptions, setCachingHeadersOnRequest
)


class CookieInstallerTests(unittest.TestCase):

	def setUp(self):
		self._reset()


	def _reset(self):
		# not very random at all
		self.c = CookieInstaller(
			secureRandom=lambda nbytes: 'x' * nbytes,
			insecureName='__',
			secureName='_s')
		self.request = http.Request(DummyChannel(), None)


	def test_installsCookieOnCookielessRequest(self):
		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual(
			['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/' % (
				base64.b64encode('x' * 16),)],
			self.request.cookies)


	def test_installsSecureCookieOnCookielessRequestHTTPS(self):
		self.request.isSecure = lambda: True
		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual(
			['_s=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/; Secure' % (
				base64.b64encode('x' * 16),)],
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
			# TODO: maybe support padding-free base64 in future
			base64.b64encode('z' * 16).rstrip("="),
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
				['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; Path=/' % (
					base64.b64encode('x' * 16),)],
				self.request.cookies)


	def test_installsCookieWithCustomDomain(self):
		self.c = CookieInstaller(
			secureRandom=lambda nbytes: 'x' * nbytes,
			insecureName='__',
			secureName='_s',
			domain='.customdomain.com')

		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual(
			['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; '
			'Domain=.customdomain.com; Path=/' % (
				base64.b64encode('x' * 16),)],
			self.request.cookies)


	def test_installsCookieWithCustomPath(self):
		self.c = CookieInstaller(
			secureRandom=lambda nbytes: 'x' * nbytes,
			insecureName='__',
			secureName='_s',
			path='/what')

		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual(
			['__=%s; Expires=Sat, 08 Dec 2029 23:55:42 GMT; '
			'Path=/what' % (
				base64.b64encode('x' * 16),)],
			self.request.cookies)


	def test_installsCookieWithCustomExpires(self):
		self.c = CookieInstaller(
			secureRandom=lambda nbytes: 'x' * nbytes,
			insecureName='__',
			secureName='_s',
			expires='NEVER EVER')

		sess = self.c.getSet(self.request)
		self.assertEqual('x' * 16, sess)
		self.assertEqual(
			['__=%s; Expires=NEVER EVER; Path=/' % (
				base64.b64encode('x' * 16),)],
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

	def _makeSite(self, r):
		try:
			site = server.Site(r, clock=Clock())
		except TypeError:
			site = server.Site(r)
		return site


	def test_rootURLNotRedirectedWithLeafRoot(self):
		req = DummyRequest([''])
		req.uri = '/'

		r = Leaf()
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, Leaf), res)


	def test_rootURLNotRedirectedWithNonLeafRoot(self):
		# the '' is necessary for this test, not for the above
		req = DummyRequest([''])
		req.uri = '/'

		r = NonLeafWithIndexChild()
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, Leaf), res)


	def test_normalRequestNotRedirected(self):
		req = DummyRequest(['hello', ''])
		req.uri = '/hello/'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, Leaf), res)


	def test_redirectedToPathPlusSlash1(self): # For leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, RedirectingResource), res)
		self.assertEqual("/hello/", res._location)


	def test_redirectedToPathPlusSlash2(self): # For non-leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafWithIndexChild()
		r.putChild('hello', hello)
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, RedirectingResource), res)
		self.assertEqual("/hello/", res._location)


	def test_redirectedToPathPlusSlash3(self): # For non-leaf -> non-leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafWithNonLeafIndexChild()
		r.putChild('hello', hello)
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, RedirectingResource), res)
		self.assertEqual("/hello/", res._location)


	def test_normalRequestToNonLeafNonLeafNotRedirected(self):
		# ugh. need to do integration testing and send real requests
		req = DummyRequest(['hello', '', ''])
		req.uri = '/hello/'

		r = NonLeaf()
		hello = NonLeafWithNonLeafIndexChild()
		r.putChild('hello', hello)
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, Leaf), res)


	def test_notRedirectedBecauseResourceIsNotBetter1(self): # For leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = LeafPlainResource()
		r.putChild('hello', hello)
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, LeafPlainResource), res)


	def test_notRedirectedBecauseResourceIsNotBetter2(self): # For non-leaf
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafPlainResource()
		r.putChild('hello', hello)
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, NonLeafPlainResource), res)


	def test_404forStrangeResourceBecauseNoIndex(self):
		req = DummyRequest(['hello'])
		req.uri = '/hello'

		r = NonLeaf()
		hello = NonLeafWithChildChild()
		r.putChild('hello', hello)
		site = self._makeSite(r)
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
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, HelpfulNoResource), res)


	def test_404urlWithCrud(self):
		req = DummyRequest(['hello', 'there'])
		req.uri = '/hello/there'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = self._makeSite(r)
		res = site.getResourceFor(req)
		self.assertTrue(isinstance(res, HelpfulNoResource), res)


	def test_404urlWithSlashCrud(self):
		req = DummyRequest(['hello', '', '', ''])
		req.uri = '/hello///'

		r = NonLeaf()
		hello = Leaf()
		r.putChild('hello', hello)
		site = self._makeSite(r)
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
#		site = self._makeSite(r)
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
#		site = self._makeSite(r)
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
#		site = self._makeSite(r)
#		res = site.getResourceFor(req)
#		self.assertTrue(isinstance(res, RedirectingResource), res)
#		self.assertEqual("/", res._location)



class CSSCacheEntryTests(unittest.TestCase):

	def test_repr(self):
		cce = _CSSCacheEntry('processed', 'digest', [])
		self.assertEqual("<_CSSCacheEntry len(processed)=9, "
			"digest='digest', references=[]>", repr(cce))



class BetterFileTests(unittest.TestCase):

	def _makeDummyRequest(self, postpath, path, site):
		request = DummyRequest(postpath)
		if path is not None:
			request.path = path
		if site is not None:
			request.channel.site = site
		return request


	def _requestPostpathAndRender(self, baseResource, postpath, path=None, site=None):
		request = self._makeDummyRequest(postpath, path, site)
		child = resource.getChildForRequest(baseResource, request)
		d = _util._render(child, request)
		d.addCallback(lambda _: (request, child))
		return d


	def test_rewriteCss(self):
		"""
		Test that CSS processing works, and verify the header.
		"""
		clock = Clock()
		fc = FileCache(lambda: clock.seconds(), 1)
		temp = FilePath(self.mktemp() + '.css')
		with temp.open('wb') as f:
			f.write("p { color: red; }\n")

		# BetterFile(temp.path) would not work because the processing happens
		# in getChild.  So, create a BetterFile for the .css file's parent dir.
		bf = BetterFile(temp.parent().path, fileCache=fc, rewriteCss=True)
		d = self._requestPostpathAndRender(bf, [temp.basename()])

		headerRe = re.compile(r"/\* CSSResource processed ([0-9a-f]{32}?) \*/")
		def assertProcessedContent((request, child)):
			out = "".join(request.written)
			lines = out.split("\n")
			self.assertTrue(re.match(headerRe, lines[0]), lines[0])
			self.assertEqual("p { color: red; }", lines[1])
			self.assertEqual("", lines[2])
			self.assertEqual(3, len(lines))
		d.addCallback(assertProcessedContent)
		return d


	def test_cssCached(self):
		"""
		The processed CSS file is cached, and updated when the underlying
		file changes.
		"""
		clock = Clock()
		fc = FileCache(lambda: clock.seconds(), 1)
		temp = FilePath(self.mktemp() + '.css')
		temp.setContent("p { color: red; }\n")

		bf = BetterFile(temp.parent().path, fileCache=fc, rewriteCss=True)
		d = self._requestPostpathAndRender(bf, [temp.basename()])

		def assertColorRed((request, child)):
			lines = "".join(request.written).split("\n")
			self.assertEqual(["p { color: red; }", ""], lines[1:])
		d.addCallback(assertColorRed)

		def modifyUnderlyingAndMakeRequest(_):
			with temp.open('wb') as f:
				f.write("p { color: green; }\n")
			d = self._requestPostpathAndRender(bf, [temp.basename()])
			return d
		d.addCallback(modifyUnderlyingAndMakeRequest)

		def assertStillColorRed((request, child)):
			lines = "".join(request.written).split("\n")
			self.assertEqual(["p { color: red; }", ""], lines[1:])
		d.addCallback(assertStillColorRed)

		def advanceClockAndMakeRequest(_):
			clock.advance(1)
			d = self._requestPostpathAndRender(bf, [temp.basename()])
			return d
		d.addCallback(advanceClockAndMakeRequest)

		def assertColorGreen((request, child)):
			lines = "".join(request.written).split("\n")
			self.assertEqual(["p { color: green; }", ""], lines[1:])
		d.addCallback(assertColorGreen)

		return d


	def _makeTree(self):
		parent = FilePath(self.mktemp())
		parent.makedirs()
		sub = parent.child('sub')
		sub.makedirs()
		subsub = sub.child('sub sub')
		subsub.makedirs()

		parent.child('one.png').setContent("one")
		sub.child("two.png").setContent("two")
		subsub.child("three.png").setContent("three")

		t = {}
		t['md5one'] = hashlib.md5("one").hexdigest()
		t['md5two'] = hashlib.md5("two").hexdigest()
		t['md5three'] = hashlib.md5("three").hexdigest()
		t['md5replacement'] = hashlib.md5("replacement").hexdigest()

		temp = sub.child('style.css')
		original = """\
div { background-image: url(http://127.0.0.1/not-modified.png); }
td { background-image: url(https://127.0.0.1/not-modified.png); }
p { background-image: url(../one.png); }
q { background-image: url(two.png); }
b { background-image: url(sub%20sub/three.png); }
i { background-image: url(/sub/sub%20sub/three.png); }
"""
		temp.setContent(original)
		t['md5original'] = hashlib.md5(original).hexdigest()

		return parent, t


	def test_cssRewriterFixesUrls(self):
		"""
		The CSS rewriter appends ?cachebreakers to the url(...)s inside
		the .css file.  If a file mentioned by a url(...) is modified, the
		processed .css is updated.
		"""
		clock = Clock()
		fc = FileCache(lambda: clock.seconds(), 1)
		parent, t = self._makeTree()
		root = BetterFile(parent.path, fileCache=fc, rewriteCss=True)
		site = server.Site(root)

		def requestStyleCss():
			return self._requestPostpathAndRender(
				root, ['sub', 'style.css'], path='/sub/style.css', site=site)

		d = requestStyleCss()

		expect = """\
/* CSSResource processed %(md5original)s */
div { background-image: url(http://127.0.0.1/not-modified.png); }
td { background-image: url(https://127.0.0.1/not-modified.png); }
p { background-image: url(../one.png?cb=%(md5one)s); }
q { background-image: url(two.png?cb=%(md5two)s); }
b { background-image: url(sub%%20sub/three.png?cb=%(md5three)s); }
i { background-image: url(/sub/sub%%20sub/three.png?cb=%(md5three)s); }
"""

		def assertCacheBrokenLinks((request, child)):
			out = "".join(request.written)
			self.assertEqual(expect % t, out,
				"\nExpected:\n\n%s\n\nGot:\n\n%s" % (expect % t, out))
			expectedBreaker = hashlib.md5(expect % t).hexdigest()
			self.assertEqual(expectedBreaker, child.getCacheBreaker())
		d.addCallback(assertCacheBrokenLinks)

		def modifyThreePngAndMakeRequest(_):
			parent.child('sub').child('sub sub').child('three.png').setContent("replacement")
			return requestStyleCss()
		d.addCallback(modifyThreePngAndMakeRequest)

		def assertNotUpdatedLinks((request, child)):
			out = "".join(request.written)
			# Still the same links, because we didn't advance the clock.
			self.assertEqual(expect % t, out)
		d.addCallback(assertNotUpdatedLinks)

		def advanceClockAndMakeRequest(_):
			clock.advance(1)
			return requestStyleCss()
		d.addCallback(advanceClockAndMakeRequest)

		def assertUpdatedLinks((request, child)):
			out = "".join(request.written)
			t2 = t.copy()
			t2['md5three'] = t['md5replacement']
			self.assertEqual(expect % t2, out)
		d.addCallback(assertUpdatedLinks)

		return d


	def test_rewriteCssButNoFileCache(self):
		self.assertRaises(
			NotImplementedError,
			lambda: BetterFile('nonexistent', rewriteCss=True))



class TestResponseCacheOptions(unittest.TestCase):

	def test_repr(self):
		rco = ResponseCacheOptions(2, True, False)
		self.assertEqual('ResponseCacheOptions(2, True, False)', repr(rco))



class TestsetCachingHeadersOnRequest(unittest.TestCase):
	"""
	Tests for L{untwist.setCachingHeadersOnRequest}
	"""
	def test_httpRequest(self):
		clock = Clock()
		rco = ResponseCacheOptions(
			cacheTime=3600, httpCachePublic=False, httpsCachePublic=True)
		request = DummyRequest([])

		setCachingHeadersOnRequest(request, rco, getTime=lambda: clock.seconds())
		self.assertEqual({
			'Cache-Control': ['max-age=3600, private'],
			'Date': ['Thu, 01 Jan 1970 00:00:00 GMT'],
			'Expires': ['Thu, 01 Jan 1970 01:00:00 GMT']},
		dict(request.responseHeaders.getAllRawHeaders()))


	def test_httpsRequest(self):
		clock = Clock()
		rco = ResponseCacheOptions(
			cacheTime=3600, httpCachePublic=False, httpsCachePublic=True)
		request = DummyRequest([])
		request.isSecure = lambda: True

		setCachingHeadersOnRequest(request, rco, getTime=lambda: clock.seconds())
		self.assertEqual({
			'Cache-Control': ['max-age=3600, public'],
			'Date': ['Thu, 01 Jan 1970 00:00:00 GMT'],
			'Expires': ['Thu, 01 Jan 1970 01:00:00 GMT']},
		dict(request.responseHeaders.getAllRawHeaders()))


	def test_requestAlreadyHasHeaders(self):
		"""
		If the request passed to L{setCachingHeadersOnRequest} already has headers,
		existing Date/Expires/Cache-Control headers are replaced, and
		irrelevant ones are kept.
		"""
		clock = Clock()
		rco = ResponseCacheOptions(
			cacheTime=3600, httpCachePublic=False, httpsCachePublic=True)
		request = DummyRequest([])
		request.responseHeaders.setRawHeaders('cache-control', ['X', 'Y'])
		request.responseHeaders.setRawHeaders('date', ['whenever'])
		request.responseHeaders.setRawHeaders('expires', ['sometime'])
		request.responseHeaders.setRawHeaders('extra', ['one', 'two'])

		setCachingHeadersOnRequest(request, rco, getTime=lambda: clock.seconds())
		self.assertEqual({
			'Cache-Control': ['max-age=3600, private'],
			'Date': ['Thu, 01 Jan 1970 00:00:00 GMT'],
			'Expires': ['Thu, 01 Jan 1970 01:00:00 GMT'],
			'Extra': ['one', 'two']},
		dict(request.responseHeaders.getAllRawHeaders()))


	def test_noCache(self):
		"""
		If C{cacheTime} is 0, appropriate headers are set.
		"""
		clock = Clock()
		# Even though these are both public=True, it correctly sets ", private".
		rco = ResponseCacheOptions(
			cacheTime=0, httpCachePublic=True, httpsCachePublic=True)
		request = DummyRequest([])
		setCachingHeadersOnRequest(request, rco, getTime=lambda: clock.seconds())

		self.assertEqual({
			'Cache-Control': ['max-age=0, private'],
			# A Date header is set even in this case.
			'Date': ['Thu, 01 Jan 1970 00:00:00 GMT'],
			'Expires': ['-1']},
		dict(request.responseHeaders.getAllRawHeaders()))

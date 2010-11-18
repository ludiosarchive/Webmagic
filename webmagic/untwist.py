"""
Various features to make using twisted.web to build real websites
a bit more sane.
"""

import cgi
import binascii

from twisted.web import resource, static, http, server
from twisted.python import log

from zope.interface import implements, Interface

from mypy.transforms import md5hexdigest
from webmagic.pathmanip import ICacheBreaker


class CookieInstaller(object):
	"""
	Gets or sets a session cookie on a L{twisted.web.server.Request} object.
	"""
	__slots__ = ('_secureRandom',)

	# Sent to HTTP and HTTPS.
	insecureCookieName = '__'

	# Sent only over HTTPS. The cookie name is different so that it does not collide.
	secureCookieName = '_s'

	expires = 'Sat, 08 Dec 2029 23:55:42 GMT' # copied from Amazon

	path = '/'

	domain = None

	# TODO: maybe add some functionality to get/set the insecure cookie
	# during HTTPS requests as well.

	def __init__(self, secureRandom):
		"""
		C{secureRandom} is a 1-argument (# of bytes) callable that returns a
			string of # random bytes.
		"""
		self._secureRandom = secureRandom


	def getSet(self, request):
		"""
		Automatically read or set a session cookie on C{request},
		a L{twisted.web.server.Request} object.

		For HTTP requests, the "insecure cookie" will be read or set.
		For HTTPS requests, the "secure cookie" will be read or set.
			If it needs to be set, it will be set with the Secure flag.

		If any cookie is not valid base64, it will be ignored and replaced.
		If any cookie does not decode to 16 bytes, it will be ignored and replaced.

		@return: 16-byte session string
		@rtype: str
		"""
		secure = request.isSecure()
		if secure:
			k = self.secureCookieName
		else:
			k = self.insecureCookieName

		existingCookie = request.getCookie(k)

		# If we allow base64 without padding, change to allow both 22 and 24.
		if existingCookie and len(existingCookie) == 24:
			try:
				# Keep in mind that a2b_base64 will skip over non-base64-alphabet characters.
				decoded = binascii.a2b_base64(existingCookie)
				if len(decoded) == 16:
					return decoded
			except binascii.Error:
				pass

		rand = self._secureRandom(16)
		v = binascii.b2a_base64(rand).rstrip('\n')
		request.addCookie(k, v, expires=self.expires, domain=self.domain, path=self.path, secure=secure)
		return rand



class HelpfulNoResource(resource.ErrorPage):
	template = """\
<!doctype html>
<html>
<head>
	<meta http-equiv="content-type" content="text/html; charset=UTF-8">
	<title>%(brief)s</title>
</head>
<body>
	<h1>%(brief)s</h1>
	<p>%(detail)s</p>
</body>
</html>"""

	def __init__(self, message='Page not found. <a href="/">See the index?</a>'):
		resource.ErrorPage.__init__(
			self, 404, "404 Not Found", message)



class RedirectingResource(resource.Resource):
	template = """\
<!doctype html>
<html>
<head>
	<meta http-equiv="content-type" content="text/html; charset=UTF-8">
	<title>Redirecting to %(escaped)s</title>
</head>
<body>
	Redirecting to <a href="%(escaped)s">%(escaped)s</a>
</body>
</html>"""

	def __init__(self, code, location):
		"""
		C{code} is the HTTP response code for the redirect, typically 301 or 302,
		but possibly 303 or 307.
		C{location} is the relative or absolute URL to redirect to.
		"""
		resource.Resource.__init__(self)
		self._code = code
		self._location = location


	def render(self, request):
		request.setResponseCode(self._code)
		# twisted.web z9trunk protects against response-splitting, so we don't
		# need to do anything to the Location header.
		# Also, this is a relative redirect; non-standard, but all browsers accept it.
		request.responseHeaders._rawHeaders['location'] = [self._location]
		return self.template % {'escaped': cgi.escape(self._location)}



class BetterResource(resource.Resource):
	"""
	By default, twisted.web Resources with `isLeaf = True`:
		- do not serve 404s if a URL is accessed as /page/extracrud
		- do not redirect /page -> /page/, or /cat/page -> /cat/page/

	Also, when /page is fetched, twisted.web Resource calls a render_*
	method, and when /page/ is fetched, it looks up /page/'s children.
	This aims to normalize the behavior, such that it looks for /page/'s
	children even when either /page or /page/ are fetched.
	"""

	# TODO: allow customizing behavior: options addSlashes and rejectExtra.

#	def __init__(self):
#		resource.Resource.__init__(self)


	def getChildWithDefault(self, path, request):
		"""
		We want to serve the same 404 page for these two cases:
			- resource was not found in self.children
			- resource was found but there was postpath crud
				Why 404 these URLs? To make sure people know
				it's not okay to link to them.

		The implementation is not eager to add slashes first. If the resource
		won't be found anyway, it returns 404s instead of redirects.
		"""
		##noisy = False

		##if noisy: print "XXX", self, 'looking at path', path
		##if noisy: print "XXX", request.prepath, request.postpath, request.uri
		##if noisy: print "XXX", request.prePathURL(), request.URLPath()

		# 404 requests for which there is no suitable Resource
		if not path in self.children:
			##if noisy: print "XXX Returning 404 because no suitable resource"
			return HelpfulNoResource()

		# 404 requests that have extra crud
		if self.children[path].isLeaf and request.postpath not in ([], ['']):
			##if noisy: print "XXX Returning 404 because request has extra crud"
			return HelpfulNoResource()

		# Redirect from /page -> /page/ and so on. This needs to happen even
		# if not `self.children[path].isLeaf`.
		# Note: static.File instances are not `isLeaf`
		if request.postpath == [] and request.prepath[-1] != '' and isinstance(self.children[path], BetterResource):
			# Avoid redirecting if the '' child for the target Resource doesn't exist
			if not ('' in self.children[path].children or self.children[path].isLeaf):
				##if noisy: print "XXX Returning 404 because target resource doesn't exist anyway"
				return HelpfulNoResource()

			# This is a non-standard relative redirect, which all browsers support.
			# Note that request.uri are the raw octets that client sent in their GET/POST line.
			##if noisy: print "XXX Redirecting to", request.uri + '/'
			return RedirectingResource(301, request.uri + '/')

		return self.children[path]



def loadCompatibleMimeTypes():
	# Read from Python's built-in mimetypes, but don't load any mimetypes
	# from disk.
	contentTypes = static.loadMimeTypes(mimetype_locations=())
	# Send the mimetypes that Google sends. These were captured on 2010-06-09.
	contentTypes.update({
		'.js': 'text/javascript',
		'.ico': 'image/x-icon',
		'.log': 'text/plain',
	})
	return contentTypes


class _CSSCacheEntry(object):
	__slots__ = ('processed', 'digest', 'references')

	def __init__(self, processed, digest, references):
		"""
		C{processed} is a C{str} containing the processed CSS file
		with the rewritten url(...)s.

		C{digest} is a C{str} containing a cachebreaker computed from the
		contents of C{processed}.

		C{references} is a C{list} of L{FilePath}s that may affect the
		content of C{processed}.
		"""
		self.processed = processed
		self.digest = digest
		self.references = references


	def __repr__(self):
		return '<%s len(processed)=%r, digest=%r, references=%r>' % (
			self.__class__.__name__,
			len(self.processed), self.digest, self.references)



class CSSResource(BetterResource):
	implements(ICacheBreaker)
	isLeaf = True

	def __init__(self, fileCache, cssCache, path):
		"""
		C{fileCache} is a L{filecache.FileCache}.

		C{cssCache} is a C{dict} mapping filenames to L{_CSSCacheEntry}
		objects.

		C{path} is a C{str} representing the absolute path of the .css file.
		"""
		BetterResource.__init__(self)
		self._fileCache = fileCache
		self._cssCache = cssCache
		self._path = path


	def _process(self, content):
		"""
		Return the processed CSS file as a C{str} and a C{list} of
		absolute paths whose contents affect the processed CSS file.
		"""
		return '/* Processed by CSSResource */\n' + content, []


	def _getProcessedCSS(self):
		"""
		Get processed CSS (new or from cache), and update the cache entry
		if necessary.
		"""
		content, maybeNew = self._fileCache.getContent(self._path)
		anyUpdatedReferences = False # TODO
		if not maybeNew and not anyUpdatedReferences:
			try:
				entry = self._cssCache[self._path]
				return entry.processed
			except KeyError:
				pass

		processed, references = self._process(content)
		entry = _CSSCacheEntry(processed, md5hexdigest(processed), references)
		self._cssCache[self._path] = entry

		return processed


	def getCacheBreaker(self):
		try:
			return self._cssCache[self._path].digest
		except KeyError:
			self._getProcessedCSS()
			return self._cssCache[self._path].digest


	def render_GET(self, request):
		request.responseHeaders.setRawHeaders('content-type',
			['text/css; charset=UTF-8'])
		# TODO: cache forever header

		return self._getProcessedCSS()



def makeCssRewriter(cssCache, fileCache):
	def cssRewriter(path, registry):
		"""
		C{path} is a C{str} representing the absolute path of the .css file.
		"""
		return CSSResource(fileCache, cssCache, path)

	return cssRewriter



class BetterFile(static.File):
	"""
	A L{static.File} that does not read any mimetypes from disk, to make sure
	no accidental dependencies on on-disk files are created.

	Also use mimetypes for maximum compatibility, instead of the ones
	that are most-correct.

	Also only allows index.html as the index page.
	"""
	contentTypes = loadCompatibleMimeTypes()

	indexNames = ["index.html"]

	def __init__(self, *args, **kwargs):
		"""
		If rewriteCss=True, you must also pass a fileCache.  Do not use
		rewriteCss=True if this directory contains untrusted CSS files,
		because files referenced by the .css file may become permanently
		cached.
		"""
		fileCache = kwargs.pop('fileCache', None)
		rewriteCss = kwargs.pop('rewriteCss', None)
		static.File.__init__(self, *args, **kwargs)
		self._cssCache = None
		if rewriteCss:
			if not fileCache:
				raise NotImplementedError(
					"If rewriteCss is true, you must also give a fileCache.")
			# a dict of (absolute path) -> _CSSCacheEntry
			self._cssCache = {}
			self.processors['.css'] = makeCssRewriter(self._cssCache, fileCache)


	def createSimilarFile(self, path):
		f = static.File.createSimilarFile(self, path)
		f._cssCache = self._cssCache
		return f



class ConnectionTrackingHTTPChannel(http.HTTPChannel):
	"""
	An L{HTTPChannel} that tells the factory about all connection
	activity.
	"""
	__slots__ = ()

	def __init__(self, *args, **kwargs):
		http.HTTPChannel.__init__(self, *args, **kwargs)


	def connectionMade(self, *args, **kwargs):
		http.HTTPChannel.connectionMade(self, *args, **kwargs)
		log.msg('Connection made: %r' % (self,))
		self.factory.connections.add(self)


	def connectionLost(self, *args, **kwargs):
		http.HTTPChannel.connectionLost(self, *args, **kwargs)
		log.msg('Connection lost: %r' % (self,))
		self.factory.connections.remove(self)



class ConnectionTrackingSite(server.Site):
	protocol = ConnectionTrackingHTTPChannel

	def __init__(self, *args, **kwargs):
		server.Site.__init__(self, *args, **kwargs)
		self.connections = set()



class DisplayConnections(BetterResource):
	"""
	Display a list of all connections connected to this server.
	You might not need this, because ConnectionTrackingHTTPChannel
	emits log messages.
	"""
	isLeaf = True
	def render_GET(self, request):
		conns = repr(request.channel.factory.connections)
		out = """\
<pre>
%s
</pre>
""" % (cgi.escape(conns),)
		return out

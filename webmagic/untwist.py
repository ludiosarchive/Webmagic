"""
Various features to make using twisted.web to build real websites
a bit more sane.
"""

import sys
import binascii
import cgi
import time
from functools import partial

from twisted.web import resource, static, server
try:
	# Twisted >= 9.0
	from twisted.web.resource import ErrorPage
except ImportError:
	from twisted.web.error import ErrorPage

from twisted.web.http import HTTPChannel, datetimeToString
from twisted.python import context, log

from zope.interface import implements

from webmagic.transforms import md5hexdigest
from webmagic.pathmanip import ICacheBreaker
from webmagic.cssfixer import fixUrls
from webmagic.safe_headers import setRawHeadersSafely

_postImportVars = vars().keys()


class CookieInstaller(object):
	"""
	Gets or sets an 16-byte identifier cookie on a L{twisted.web.server.Request}
	object.
	"""
	__slots__ = ('_secureRandom', '_insecureName', '_secureName', '_domain',
		'_path', '_expires')

	# TODO: maybe add some functionality to get/set the insecure cookie
	# during HTTPS requests as well.

	def __init__(self, secureRandom, insecureName, secureName,
	domain=None, path='/', expires='Sat, 08 Dec 2029 23:55:42 GMT'):
		"""
		@param secureRandom: a 1-argument (# of bytes) callable that
			returns a string of # random bytes.  You probably want to
			pass L{os.urandom}.
		@type secureRandom: function

		@param insecureName: the cookie name for a cookie that will be sent by
			client for both HTTP and HTTPS requests.
		@type insecureName: C{str}

		@param secureName: the cookie name for a cookie that will be sent by
			client for HTTPS requests.  Don't use the same name as C{insecureName}.
		@type secureName: C{str}
		"""
		self._secureRandom = secureRandom
		self._insecureName = insecureName
		self._secureName = secureName
		self._domain = domain
		self._path = path
		self._expires = expires


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
			k = self._secureName
		else:
			k = self._insecureName

		existingCookie = request.getCookie(k)

		# If we ever allow base64 without padding, change to allow both 22 and 24.
		if existingCookie and len(existingCookie) == 24:
			try:
				# Keep in mind that a2b_base64 will skip over
				# non-base64-alphabet characters.
				decoded = binascii.a2b_base64(existingCookie)
				if len(decoded) == 16:
					return decoded
			except binascii.Error:
				pass

		rand = self._secureRandom(16)
		v = binascii.b2a_base64(rand).rstrip('\n')
		request.addCookie(k, v, expires=self._expires, domain=self._domain,
			path=self._path, secure=secure)
		return rand



def setDefaultHeadersOnRequest(request):
	setRawHeaders = request.responseHeaders.setRawHeaders

	# http://hackademix.net/2009/11/21/ies-xss-filter-creates-xss-vulnerabilities/
	# Since the March 2010 update, Internet Explorer 8 also supports the
	# X-XSS-Protection: 1; mode=block header.  Google now uses this.
	setRawHeaders('x-xss-protection', ['1; mode=block'])

	# Prevent IE8 from from mime-sniffing a response.
	setRawHeaders('x-content-type-options', ['nosniff'])

	# twisted.web.server sets "text/html", which sometimes leads to XSS
	# due to UTF-7 sniffing in IE6 and IE7.
	setRawHeaders('content-type', ['text/html; charset=UTF-8'])


def setCachingHeadersOnRequest(request, cacheOptions, getTime=time.time):
	cacheTime = cacheOptions.cacheTime
	setRawHeaders = request.responseHeaders.setRawHeaders

	timeNow = getTime()
	# Even though twisted.web sets a Date header, set one ourselves to
	# make sure that Date + cacheTime == Expires.
	setRawHeaders('date', [datetimeToString(timeNow)])

	if cacheTime != 0:
		isSecure = request.isSecure()
		if isSecure and cacheOptions.httpsCachePublic:
			privacy = 'public'
		elif not isSecure and cacheOptions.httpCachePublic:
			privacy = 'public'
		else:
			privacy = 'private'

		setRawHeaders('expires',
			[datetimeToString(timeNow + cacheOptions.cacheTime)])
		setRawHeaders('cache-control',
			['max-age=%d, %s' % (cacheOptions.cacheTime, privacy)])
	else:
		setRawHeaders('expires', ['-1'])
		setRawHeaders('cache-control', ['max-age=0, private'])


def setNoCacheNoStoreHeaders(request):
	setRawHeaders = request.responseHeaders.setRawHeaders

	# Headers are similar to the ones gmail sends
	setRawHeaders('cache-control', [
		'no-cache, no-store, max-age=0, must-revalidate'])
	setRawHeaders('pragma', ['no-cache'])
	setRawHeaders('expires', ['-1'])


class HelpfulNoResource(ErrorPage):
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
		ErrorPage.__init__(
			self, 404, "404 Not Found", message)


	def render(self, request):
		setDefaultHeadersOnRequest(request)
		return ErrorPage.render(self, request)



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
		setDefaultHeadersOnRequest(request)
		request.setResponseCode(self._code)
		# This is a relative redirect, so it is non-standard, but all
		# browsers accept it.
		setRawHeadersSafely(
			request.responseHeaders, 'location', [self._location])
		return self.template % {'escaped': cgi.escape(self._location)}



class BetterResource(resource.Resource):
	"""
	A L{resource.Resource} with several improvements:

	*	/page and /page/ are forced to be the same thing (/page is
		redirected to /page/)

	*	Additional response headers are set for security reasons.

	*	Cache-related headers are removed if an exception was raised from
		render().

	Implementation notes:

	By default, twisted.web Resources with `isLeaf = True`:
		- do not serve 404s if a URL is accessed as /page/extracrud
		- do not redirect /page -> /page/, or /cat/page -> /cat/page/

	Also, when /page is fetched, twisted.web Resource calls a render_*
	method, and when /page/ is fetched, it looks up /page/'s children.
	This aims to normalize the behavior, such that it looks for /page/'s
	children even when either /page or /page/ are fetched.
	"""
	_debugGetChild = False

	# TODO: allow customizing behavior: options addSlashes and rejectExtra.

	def render(self, request):
		setDefaultHeadersOnRequest(request)
		try:
			return resource.Resource.render(self, request)
		except:
			# Set no-cache headers, to make sure the error page doesn't
			# get cached.
			setNoCacheNoStoreHeaders(request)
			# re-raise the exception, resulting in a call to
			# twisted.web.server.Request.processingFailed
			raise


	def getChild(self, path, request):
		"""
		Works like L{resource.Resource.getChild}:

		Retrieve a 'child' resource from me.

		Implement this to create dynamic resource generation -- resources which
		are always available may be registered with self.putChild().

		BetterResource-specific:

		All that's implemented by default beyond a L{resource.Resource}
		is to replace the 404 page with a slightly better one.

		Note that what L{getChildWithDefault} enforces on resources
		with trailing crud, and what it implements for redirecting
		paths without slashes, is not implemented here for dynamic
		resources.  Subclasses should implement this behavior themselves
		if it is desired.
		"""
		if self._debugGetChild:
			log.msg("BetterResource: Returning 404 "
				"because no suitable resource")
		return HelpfulNoResource()


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
		if self._debugGetChild:
			log.msg("BetterResource: %r looking at path %r" % (self, path))
			log.msg("BetterResource: prepath=%r postpath=%r uri=%r" % (
				request.prepath, request.postpath, request.uri))

		# Like resource.Resource, give getChild a chance to respond
		# with a dynamic resource for paths that aren't in self.children
		if not path in self.children:
			return self.getChild(path, request)

		# 404 requests that have extra crud
		if self.children[path].isLeaf and request.postpath not in ([], ['']):
			if self._debugGetChild:
				log.msg("BetterResource: Returning 404 "
					"because request has extra crud")
			return HelpfulNoResource()

		# Redirect from /page -> /page/ and so on. This needs to happen even
		# if not `self.children[path].isLeaf`.
		# Note: static.File instances are not `isLeaf`
		if request.postpath == [] and request.prepath[-1] != '' and \
		isinstance(self.children[path], BetterResource):
			# Avoid redirecting if the '' child for the target Resource doesn't exist
			if not ('' in self.children[path].children or self.children[path].isLeaf):
				if self._debugGetChild:
					log.msg("BetterResource: Returning 404 "
						"because target resource doesn't exist anyway")
				return HelpfulNoResource()

			# This is a non-standard relative redirect, which all
			# browsers support.  Note that request.uri are the raw octets
			# that client sent in their GET/POST line.
			target = request.uri + '/'
			if self._debugGetChild:
				log.msg("BetterResource: Redirecting to %r" % (target,))
			return RedirectingResource(301, target)

		return self.children[path]



def loadCompatibleMimeTypes():
	# Read from Python's built-in mimetypes, but don't load any mimetypes
	# from disk.
	contentTypes = static.loadMimeTypes(mimetype_locations=())
	contentTypes.update({
		# Use text/javascript instead of application/javascript for
		# compatibility reasons.
		'.js': 'text/javascript',
		'.ico': 'image/x-icon',
		'.log': 'text/plain',
		'.rst': 'text/plain',

		# Office 2007 formats
		# http://technet.microsoft.com/en-us/library/ee309278%28office.12%29.aspx
		'.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
		'.docm': 'application/vnd.ms-word.document.macroEnabled.12',
		'.dotx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.template',
		'.dotm': 'application/vnd.ms-word.template.macroEnabled.12',
		'.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
		'.xlsm': 'application/vnd.ms-excel.sheet.macroEnabled.12',
		'.xltx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.template',
		'.xltm': 'application/vnd.ms-excel.template.macroEnabled.12',
		'.xlsb': 'application/vnd.ms-excel.sheet.binary.macroEnabled.12',
		'.xlam': 'application/vnd.ms-excel.addin.macroEnabled.12',
		'.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
		'.pptm': 'application/vnd.ms-powerpoint.presentation.macroEnabled.12',
		'.ppsx': 'application/vnd.openxmlformats-officedocument.presentationml.slideshow',
		'.ppsm': 'application/vnd.ms-powerpoint.slideshow.macroEnabled.12',
		'.potx': 'application/vnd.openxmlformats-officedocument.presentationml.template',
		'.potm': 'application/vnd.ms-powerpoint.template.macroEnabled.12',
		'.ppam': 'application/vnd.ms-powerpoint.addin.macroEnabled.12',
		'.sldx': 'application/vnd.openxmlformats-officedocument.presentationml.slide',
		'.sldm': 'application/vnd.ms-powerpoint.slide.macroEnabled.12',
		'.one': 'application/onenote',
		'.onetoc2': 'application/onenote',
		'.onetmp': 'application/onenote',
		'.onepkg': 'application/onenote',
		'.thmx': 'application/vnd.ms-officetheme',
	})
	return contentTypes


class ResponseCacheOptions(object):
	__slots__ = ('cacheTime', 'httpCachePublic', 'httpsCachePublic')

	def __init__(self, cacheTime, httpCachePublic, httpsCachePublic):
		"""
		@param cacheTime: Send headers that indicate that this resource
			(and children) should be cached for this many seconds.  Don't
			set this to over 1 year, because that violates the RFC
			guidelines.

		@param httpCachePublic: If true, for HTTP requests, send
			"Cache-control: public" instead of "Cache-control: private".
			Don't use this for gzip'ed resources because of buggy proxies;
			see http://code.google.com/speed/page-speed/docs/caching.html

		@param httpsCachePublic: If true, for HTTPS requests, send
			"Cache-control: public" instead of "Cache-control: private".
			This is useful for making Firefox 3+ cache HTTPS resources
			to disk.
		"""
		assert cacheTime >= 0, cacheTime
		self.cacheTime = cacheTime
		self.httpCachePublic = httpCachePublic
		self.httpsCachePublic = httpsCachePublic


	def __repr__(self):
		return '%s(%r, %r, %r)' % (
			self.__class__.__name__,
			self.cacheTime, self.httpCachePublic, self.httpsCachePublic)



class _CSSCacheEntry(object):
	__slots__ = ('processed', 'digest', 'references')

	def __init__(self, processed, digest, references):
		"""
		@param processed: a C{str} containing the processed CSS file
			with the rewritten url(...)s.

		@param digest: a C{str} containing a cachebreaker computed from
			the contents of C{processed}.

		@param references: a C{list} of L{ReferencedFile}s that may affect
			the content of C{processed}.
		"""
		assert not isinstance(processed, unicode), type(processed)
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

	def __init__(self, topLevelBF, request, path):
		"""
		@param topLevelBF: a L{BetterFile}.
		@param request: the L{server.Request} that is requesting this
			resource.  Note: L{BetterFile} instantiates a new CSSResource
			for each request.
		@param path: a C{str}, the absolute path of the .css file.
		"""
		BetterResource.__init__(self)

		self._cssCache = topLevelBF._cssCache
		self._getTime = topLevelBF._getTime
		self._fileCache = topLevelBF._fileCache
		self._responseCacheOptions = topLevelBF._responseCacheOptions

		self._request = request
		self._path = path


	def _process(self, content):
		"""
		@return: the processed CSS file as a C{str} and a C{list} of
			L{ReferencedFile}s whose contents affect the processed CSS
			file.
		"""
		fixedContent, references = fixUrls(self._fileCache, self._request, content)
		out = '/* CSSResource processed %s */\n%s' % (
			md5hexdigest(content), fixedContent)
		return out, references


	def _haveUpdatedReferences(self):
		"""
		@return: a C{bool}, whether any of the files referenced by the .css
			file have been updated.

		Note that this does not handle the obscure edge case of switching
		out the /path/s on your L{server.Site}.  It may return a false
		negative in this case.  It could be "improved" to work on this
		case, but it would be slower.
		"""
		try:
			entry = self._cssCache[self._path]
		except KeyError:
			return False

		for ref in entry.references:
			nowhash, maybeNew = self._fileCache.getContent(
				ref.path, transform=md5hexdigest)
			if ref.lasthash != nowhash:
				return True

		return False


	def _getProcessedCSS(self):
		"""
		@return: a C{str}, the processed CSS (new or from cache).

		This also updates the cache entry if necessary.
		"""
		content, maybeNew = self._fileCache.getContent(self._path)
		if not maybeNew and not self._haveUpdatedReferences():
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
		assert self._request is request, (
			"unexpected render_GET request: ",
			request, " is not ", self._request)

		# Do this before setting headers, in case it throws an exception.
		processed = self._getProcessedCSS()

		request.responseHeaders.setRawHeaders('content-type',
			['text/css; charset=UTF-8'])
		setCachingHeadersOnRequest(
			request, self._responseCacheOptions, self._getTime)

		return processed



def _cssRewriter(topLevelBF, path, registry):
	"""
	C{path} is a C{str} representing the absolute path of the .css file.
	"""
	request = context.get('_BetterFile_last_request')
	return CSSResource(topLevelBF, request, path)



class BetterFile(static.File):
	"""
	A L{static.File} with a few modifications and new features:

	*	BetterFile does not read any mimetypes from OS-specific mimetype
		files, to avoid creating accidental dependencies on them.

	*	BetterFile uses mimetypes that are maximally compatible instead of
		most-correct.

	*	BetterFile allows only index.html as the index page.

	*	BetterFile can transparently rewrite .css files to add cachebreakers
		to url(...)s inside the .css file.  (Pass in a fileCache and
		rewriteCss=True).

	*	BetterFile sets cache-related HTTP headers for you.  You can change
		the headers with the C{cacheOptions} parameter.
	"""
	contentTypes = loadCompatibleMimeTypes()

	indexNames = ["index.html"]

	def __init__(self, path, defaultType="text/html", ignoredExts=(),
	registry=None, fileCache=None, rewriteCss=False,
	responseCacheOptions=None, getTime=time.time):
		"""
		@param fileCache: a L{filecache.FileCache}, used only to cache
			resources referenced by .css files.

		@param rewriteCss: If true, transparently rewrite .css files to
			add cachebreakers.  If true, you must also pass a
			C{fileCache}.  Do not use rewriteCss if this directory
			contains untrusted CSS files, because files referenced by
			the .css file may become permanently cached.

		@param responseCacheOptions: A L{ResponseCacheOptions}.

		@param getTime: a 0-arg callable that returns the current time as
			seconds since epoch.
		"""
		static.File.__init__(self, path, defaultType, ignoredExts, registry)

		if responseCacheOptions is None:
			responseCacheOptions = ResponseCacheOptions(0, False, False)

		self._getTime = getTime
		self._fileCache = fileCache
		self._responseCacheOptions = responseCacheOptions

		self._cssCache = None
		if rewriteCss:
			if not fileCache:
				raise NotImplementedError(
					"If rewriteCss is true, you must also give a fileCache.")
			# a dict of (absolute path) -> _CSSCacheEntry
			self._cssCache = {}
			# Note how a new .processors is not created after
			# createSimilarFile, because rewriteCss is False in that
			# case.  It sets a .processors afterwards.
			self.processors['.css'] = partial(_cssRewriter, self)


	def getChild(self, path, request):
		# This is a bit of a hack, but it allows the `cssRewriter`
		# processor to grab the request (which static.File.getChild sadly
		# does not pass into it).
		return context.call(
			{'_BetterFile_last_request': request},
			static.File.getChild, self, path, request)


	def createSimilarFile(self, path):
		f = static.File.createSimilarFile(self, path)
		# Remember to be careful in BetterFile.__init__, because we don't
		# pass in any of our special attributes to the constructor.
		f._cssCache = self._cssCache
		f._getTime = self._getTime
		f._responseCacheOptions = self._responseCacheOptions
		return f


	# We don't want to cache error pages and directory listings, so we
	# set a cache header only when creating a producer to send a file.
	def makeProducer(self, request, fileForReading):
		##print "makeProducer setting cache headers:", self, self._responseCacheOptions
		setDefaultHeadersOnRequest(request)
		setCachingHeadersOnRequest(
			request, self._responseCacheOptions, self._getTime)
		return static.File.makeProducer(self, request, fileForReading)



class _BetterHTTPChannel(HTTPChannel):
	def connectionMade(self, *args, **kwargs):
		HTTPChannel.connectionMade(self, *args, **kwargs)
		if self.site._setNoDelayOnConnect and \
		hasattr(self.transport, 'setTcpNoDelay'):
			self.transport.setTcpNoDelay(True)



class BetterSite(server.Site):
	"""
	A L{server.Site} with a few modifications:

	*	Default idle (not serving a request) keep-alive timeout of 75 seconds
		instead of 12 hours.

	*	Sets TCP_NODELAY on all connections (unless disabled with
		noDelay=False).
	"""
	protocol = _BetterHTTPChannel

	def __init__(self, resource, logPath=None, timeout=75, noDelay=True):
		server.Site.__init__(self, resource, logPath, timeout)
		self._setNoDelayOnConnect = noDelay



class ConnectionTrackingHTTPChannel(_BetterHTTPChannel):
	"""
	An L{HTTPChannel} that tells the factory about all connection
	activity.
	"""
	def __init__(self, *args, **kwargs):
		_BetterHTTPChannel.__init__(self, *args, **kwargs)


	def connectionMade(self, *args, **kwargs):
		_BetterHTTPChannel.connectionMade(self, *args, **kwargs)
		log.msg('Connection made: %r' % (self,))
		self.factory.connections.add(self)


	def connectionLost(self, *args, **kwargs):
		_BetterHTTPChannel.connectionLost(self, *args, **kwargs)
		log.msg('Connection lost: %r' % (self,))
		self.factory.connections.remove(self)



class ConnectionTrackingSite(BetterSite):
	protocol = ConnectionTrackingHTTPChannel

	def __init__(self, *args, **kwargs):
		BetterSite.__init__(self, *args, **kwargs)
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



try: from refbinder.api import bindRecursive
except ImportError: pass
else: bindRecursive(sys.modules[__name__], _postImportVars)

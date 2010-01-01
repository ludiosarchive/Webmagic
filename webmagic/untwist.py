"""
Various features to make using twisted.web to build real websites
a bit more sane.
"""

import cgi
import binascii

from twisted.web import resource


class CookieInstaller(object):
	"""
	Gets or sets a session cookie on a L{twisted.web.server.Request} object.
	"""
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
		request.setHeader('Location', self._location)
		return self.template % {'escaped': cgi.escape(self._location)}



class BetterResource(resource.Resource):
	"""
	By default, twisted.web Resources:
		- do NOT serve 404s if a URL is accessed as /page/extracrud
		- do NOT redirect /page -> /page/, or /cat/page -> /cat/page/

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

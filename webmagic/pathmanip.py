from zope.interface import Interface

from mypy.transforms import md5hexdigest

try:
	from twisted.protocols._c_urlarg import unquote
except ImportError:
	from urllib import unquote

from webmagic.uriparse import urljoin
from webmagic.fakes import DummyRequest

from twisted.web.resource import getChildForRequest


class ICacheBreaker(Interface):

	def getCacheBreaker():
		"""
		Returns a C{str} for use as the cachebreaker in a URL that points
		to this resource.  Use an md5sum, a timestamp, or something
		similar.
		"""


def makeRequestForPath(site, path):
	"""
	C{site} is a L{server.Site}.
	C{path} is a C{str} URL-encoded path that starts with C{"/"}.

	Returns a request that requests C{path}.
	"""
	# Unquote URL with the same function that twisted.web.server uses.
	postpath = unquote(path).split('/')
	postpath.pop(0)
	dummyRequest = DummyRequest(postpath)
	dummyRequest.path = path
	dummyRequest.channel.site = site
	return dummyRequest


def getResourceForPath(site, path):
	"""
	C{site} is a L{server.Site}.
	C{path} is a C{str} URL-encoded path that starts with C{"/"}.

	Returns a resource from C{site}'s resource tree that corresponds
	to C{path}.
	"""
	rootResource = site.resource
	dummyRequest = makeRequestForPath(site, path)
	return getChildForRequest(rootResource, dummyRequest)


def getBreakerForResource(fileCache, resource):
	"""
	C{fileCache} is a L{mypy.filecache.FileCache}.
	C{resource} is a L{static.File} or a subclass, which may or may not
	provide L{ICacheBreaker}.

	Returns a C{str} representing the md5sum hexdigest of the contents of
	C{resource}.

	Warning: the contents of C{resource}'s file will be cached, and items
	may stay in this cache forever.  Don't use this on dynamically-
	generated static files.
	"""
	# First try the getCacheBreaker method on the Resource, otherwise
	# assume it is a static.File and calculate the breaker ourselves.
	getCacheBreaker = getattr(resource, 'getCacheBreaker', None)
	if getCacheBreaker:
		breaker = getCacheBreaker()
	else:
		breaker, maybeNew = fileCache.getContent(
			resource.path,
			transform=md5hexdigest)
	# TODO: Because some (terrible) proxies cache based on the
	# non-query portion of the URL, it would be nice to append
	# /cachebreaker/ instead of ?cachebreaker.  This would require
	# some work on static.File and nginx, though.
	return breaker


def getBreakerForHref(fileCache, request, href):
	"""
	See L{getCacheBrokenHref} for argument description and warning.

	Returns a C{str}, (md5sum of contents of href).
	"""
	joinedPath = urljoin(request.path, href)
	site = request.channel.site
	staticResource = getResourceForPath(site, joinedPath)
	return getBreakerForResource(fileCache, staticResource)


def getCacheBrokenHref(fileCache, request, href):
	"""
	C{fileCache} is a L{filecache.FileCache}.
	C{request} is the L{server.Request} for the page that contains C{href}.
	C{href} is a C{str}, a target pointing to a L{static.File} mounted
	somewhere on C{request}'s site.

	Returns a C{str}, C{href + '?cb=' + (md5sum of contents of href)}.

	Warning: the contents of the file at C{href} will be cached, and
	items may stay in this cache forever.  Don't use this on
	dynamically-generated static files.
	"""
	return href + '?cb=' + getBreakerForHref(fileCache, request, href)

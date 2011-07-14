import sys

from zope.interface import Interface

from urllib import unquote
from urlparse import urljoin

from webmagic.fakes import DummyRequest
from webmagic.transforms import md5hexdigest

from twisted.web.resource import getChildForRequest
try:
	# Twisted >= 9.0
	from twisted.web.resource import ErrorPage
except ImportError:
	from twisted.web.error import ErrorPage

_postImportVars = vars().keys()


class ICacheBreaker(Interface):

	def getCacheBreaker():
		"""
		@return: a C{str} for use as the cachebreaker in a URL that points
			to this resource.  Use an md5sum, a timestamp, or something
			similar.
		"""


def makeRequestForPath(site, path):
	"""
	@param site: a L{server.Site}.
	@param path: a C{str} URL-encoded path that starts with C{"/"}.

	@return: a request that requests C{path}.
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
	@param site: a L{server.Site}.
	@param path: a C{str} URL-encoded path that starts with C{"/"}.

	@return: a resource from C{site}'s resource tree that corresponds
		to C{path}.
	"""
	rootResource = site.resource
	dummyRequest = makeRequestForPath(site, path)
	return getChildForRequest(rootResource, dummyRequest)


def getResourceForHref(request, href):
	"""
	@param request: a L{Request} for the resource that contains C{href}.
	@param href: a C{str} URL-encoded href, either relative or starting with
		C{"/"}.

	@return: a resource from C{site}'s resource tree that corresponds
		to C{href}.
	"""
	joinedPath = urljoin(request.path, href)
	site = request.channel.site
	return getResourceForPath(site, joinedPath)


def getBreakerForResource(fileCache, resource):
	"""
	@param fileCache: a L{filecache.FileCache}.
	@param resource: a L{Resource}.  For a proper cachebreaker, must be a
		L{static.File} or a subclass, which may or may not provide
		L{ICacheBreaker}.

	@return: a C{str} representing the md5sum hexdigest of the contents of
		C{resource}, or C{None} if C{resource} is an L{ErrorPage}.

	Warning: the contents of C{resource}'s file will be cached, and items
	may stay in this cache forever.  Don't use this on dynamically-
	generated static files.
	"""
	if isinstance(resource, ErrorPage):
		return None
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

	@return: a C{str}, (md5sum hexdigest of resource at href, or
		C{None} if resource not found).
	"""
	return getBreakerForResource(fileCache, getResourceForHref(request, href))


def makeLinkWithBreaker(href, breakerOrNone):
	"""
	@param href: a C{str}.
	@param breakerOrNone: a C{str} or C{None}.

	@return: a C{str}.
	"""
	if breakerOrNone is None:
		breakerOrNone = 'not-found'
	return href + '?cb=' + breakerOrNone


def getCacheBrokenHref(fileCache, request, href):
	"""
	@param fileCache: a L{filecache.FileCache}.
	@param request: the L{server.Request} for the page that contains C{href}.
	@param href: a C{str}, a target pointing to a L{static.File} mounted
		somewhere on C{request}'s site.

	@return: a C{str}, C{href + '?cb=' + (md5sum hexdigest of resource at href)}.

	Warning: the contents of the file at C{href} will be cached, and
	items may stay in this cache forever.  Don't use this on
	dynamically-generated static files.
	"""
	return makeLinkWithBreaker(href, getBreakerForHref(fileCache, request, href))


try: from refbinder.api import bindRecursive
except ImportError: pass
else: bindRecursive(sys.modules[__name__], _postImportVars)

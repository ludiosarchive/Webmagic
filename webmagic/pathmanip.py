from zope.interface import Interface

from mypy.transforms import md5hexdigest

from webmagic.uriparse import urljoin

from twisted.web.test.test_web import DummyRequest
from twisted.web.resource import getChildForRequest


class ICacheBreaker(Interface):

	def getCacheBreaker():
		"""
		Returns a C{str} for use as the cachebreaker in a URL that points
		to this resource.  Use an md5sum, a timestamp, or something
		similar.
		"""



def getResourceForPath(site, path):
	"""
	C{site} is a L{server.Site}.
	C{path} is a C{str} path that starts with C{"/"}.

	Returns a resource from C{site}'s resource tree that corresponds
	to C{path}.
	"""
	rootResource = site.resource
	postpath = path.split('/')
	postpath.pop(0)
	dummyRequest = DummyRequest(postpath)
	return getChildForRequest(rootResource, dummyRequest)


def makeCacheBreakLink(fileCache, request):
	def cacheBreakLink(href):
		"""
		A function that takes an C{href} and returns
		C{href + '?cb=' + (md5sum of contents of href)}.

		This requires that C{href} is somewhere on the L{site.Site}'s
		resource tree and that it is a L{static.File}.

		Warning: the contents of the file at C{href} will be cached, and
		items from this cache are never removed.  Don't use this on
		dynamically-generated static files.
		"""
		joinedPath = urljoin(request.path, href)
		site = request.channel.site
		staticResource = getResourceForPath(site, joinedPath)
		# First try the getCacheBreaker method on the Resource, otherwise
		# assume it is a static.File and calculate the breaker ourselves.
		getCacheBreaker = getattr(staticResource, 'getCacheBreaker', None)
		if getCacheBreaker:
			breaker = getCacheBreaker()
		else:
			breaker, maybeNew = fileCache.getContent(
				staticResource.path,
				transform=md5hexdigest)
		# TODO: Because some (terrible) proxies cache based on the
		# non-query portion of the URL, it would be nice to append
		# /cachebreaker/ instead of ?cachebreaker.  This would require
		# some work on static.File and nginx, though.
		return href + '?cb=' + breaker

	return cacheBreakLink

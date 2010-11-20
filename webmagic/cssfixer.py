import re
import cssutils
import operator

from webmagic.uriparse import urljoin
from webmagic.pathmanip import getResourceForHref, getBreakerForResource

_postImportVars = vars().keys()


# TODO: actually parse the CSS file
def _getUrlsHack(s):
	matches = re.findall(r'url\(.*?\)', s)
	for m in matches:
		yield m[4:-1]


class ReferencedFile(tuple):
	"""
	Represents a file referenced by a .css file and its last-known md5sum
	(as a hexdigest).
	"""
	__slots__ = ()
	_MARKER = object()

	path = property(operator.itemgetter(1))
	lastmd5 = property(operator.itemgetter(2))

	def __new__(cls, path, lastmd5):
		return tuple.__new__(cls, (cls._MARKER, path, lastmd5))


	def __repr__(self):
		return '%s(%r, %r)' % (self.__class__.__name__, self[1], self[2])



def fixUrls(fileCache, request, content):
	"""
	@param fileCache: a L{filecache.FileCache}, used to read files mentioned in
		the CSS file.
	@param request: the L{server.Request} for the .css file.
	@param content: a C{str} representing the content of the original .css file.

	@return: (the processed CSS file as a C{str},
		and a C{list} of tuples absolute paths
		whose contents affect the processed CSS file.  The processed CSS
		file has cachebreakers attached to each url(...) whose contents can
		be located on disk.

	Warning: because this function may permanently cache any file on the Site
	associated with the request, you should not pass untrusted CSS files.
	"""
	references = []
	urls = _getUrlsHack(content)
	for href in urls:
		if href.startswith('http://') or href.startswith('https://'):
			pass
		else:
			# Note: in a .css file, the href of the url(...) is relative to the .css file.
			staticResource = getResourceForHref(request, href)
			breaker = getBreakerForResource(fileCache, staticResource)
			cbLink = href + '?cb=' + breaker
			references.append(ReferencedFile(staticResource.path, breaker))
			# TODO: don't do this
			content = content.replace("url(%s)" % href, "url(%s)" % cbLink, 1)

	return content, references


from pypycpyo import optimizer
optimizer.bind_all_many(vars(), _postImportVars)

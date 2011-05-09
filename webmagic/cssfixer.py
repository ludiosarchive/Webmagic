import sys
import re
import operator

from webmagic.pathmanip import (
	getResourceForHref, getBreakerForResource, makeLinkWithBreaker)

_postImportVars = vars().keys()


# TODO: actually parse the CSS file
def _getUrlsHack(s):
	matches = re.findall(r'url\(.*?\)', s)
	for m in matches:
		yield m[4:-1]


class ReferencedFile(tuple):
	"""
	Represents a file referenced by a .css file and its last-known hash.
	"""
	__slots__ = ()
	_MARKER = object()

	path = property(operator.itemgetter(1))
	lasthash = property(operator.itemgetter(2))

	def __new__(cls, path, lasthash):
		return tuple.__new__(cls, (cls._MARKER, path, lasthash))


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
	missingBreakers = []
	for href in urls:
		if href.startswith('http://') or href.startswith('https://'):
			pass
		else:
			# Note: in a .css file, the href of the url(...) is relative to the .css file.
			staticResource = getResourceForHref(request, href)
			breaker = getBreakerForResource(fileCache, staticResource)
			if breaker is not None:
				references.append(ReferencedFile(staticResource.path, breaker))
			else:
				missingBreakers.append(href)
			# TODO: don't do this
			content = content.replace(
				"url(%s)" % href,
				"url(%s)" % makeLinkWithBreaker(href, breaker), 1)
			if missingBreakers:
				content += """\
body:before {
	content: "Warning: webmagic.cssfixer could not add cachebreakers in %r for %r";
	position: relative;
	z-index: 1000000;
	font-size: 16px;
	color: darkred;
	background-color: white;
}
""" % (request.path, missingBreakers)

	return content, references


try: from refbinder.api import bindRecursive
except ImportError: pass
else: bindRecursive(sys.modules[__name__], _postImportVars)

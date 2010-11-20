import re
import cssutils

from webmagic.uriparse import urljoin
from webmagic.pathmanip import getResourceForHref, getBreakerForResource

_postImportVars = vars().keys()


# TODO: actually parse the CSS file
def _getUrlsHack(s):
	matches = re.findall(r'url\(.*?\)', s)
	for m in matches:
		yield m[4:-1]


def fixUrls(fileCache, request, content):
	"""
	@param fileCache: a L{filecache.FileCache}, used to read files mentioned in
		the CSS file.
	@param request: the L{server.Request} for the .css file.
	@param content: a C{str} representing the content of the original .css file.

	@return: the processed CSS file as a C{str} and a C{list} of absolute paths
		whose contents affect the processed CSS file.  The processed CSS
		file has cachebreakers attached to each url(...) whose contents can
		be located on disk.

	Warning: because this function may permanently cache any file on the Site
	associated with the request, you should not pass untrusted CSS files.
	"""
	fnames = []
	urls = _getUrlsHack(content)
	for href in urls:
		if href.startswith('http://') or href.startswith('https://'):
			pass
		else:
			# Note: in a .css file, the href of the url(...) is relative to the .css file.
			staticResource = getResourceForHref(request, href)
			cbLink = href + '?cb=' + getBreakerForResource(fileCache, staticResource)
			fnames.append(staticResource.path)
			# TODO: don't do this
			content = content.replace("url(%s)" % href, "url(%s)" % cbLink, 1)

	return content, fnames


from pypycpyo import optimizer
optimizer.bind_all_many(vars(), _postImportVars)

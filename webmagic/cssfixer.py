import re
import cssutils

from webmagic.uriparse import urljoin
from webmagic.pathmanip import getResourceForPath, getBreakerForResource


# TODO: actually parse the CSS file
def _getUrlsHack(s):
	matches = re.findall(r'url\(.*?\)', s)
	for m in matches:
		yield m[4:-1]


def fixUrls(fileCache, request, content):
	"""
	Return the processed CSS file as a C{str} and a C{list} of absolute paths
	whose contents affect the processed CSS file.  The processed CSS file
	has cachebreakers attached to each url(...) whose contents can be
	located on disk.

	Because this function may permanently cache any file on the Site
	associated with the request, you should not pass untrusted CSS files.

	C{fileCache} is a L{filecache.FileCache}, used to read files mentioned in
	the CSS file.

	C{request} is the L{server.Request} for the .css file.

	C{content} is a C{str} representing the content of the original .css file.

	Returns a C{str} representing the processed CSS file, and a C{list} of
	filenames whose contents affect the processed CSS file.
	"""
	fnames = []
	urls = _getUrlsHack(content)
	for href in urls:
		if href.startswith('http://') or href.startswith('https://'):
			pass
		else:
			# CSS works like this: the href is relative to the .css file.
			joinedPath = urljoin(request.path, href)
			site = request.channel.site
			staticResource = getResourceForPath(site, joinedPath)
			cbLink = href + '?cb=' + getBreakerForResource(fileCache, staticResource)
			fnames.append(staticResource.path)
			# TODO: don't do this
			content = content.replace("url(%s)" % href, "url(%s)" % cbLink, 1)

	return content, fnames
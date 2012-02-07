"""
Header-setting functions for twisted.web.http_headers.Headers that protect
against response-splitting attacks.
"""

import sys

_postImportVars = vars().keys()


# We used to allow LF in the value if the next line were indented, but it
# was discovered[1] that CR could be used to split a value into multiple
# header fields, at least in Chrome and IE.  Therefore, to be safe against
# other buggy HTTP peers, we no longer allow CR or LF anywhere in the header.
#
# [1] https://bugs.php.net/bug.php?id=60227
def isValidHeaderValue(value):
	"""
	Checks whether the input string is a valid HTTP header value (i.e. does
	not cause a message header to split into multiple message headers).

	@type value: C{str}
	@param value: HTTP header value

	@rtype: bool
	@return: Whether the header value is valid.
	"""
	return not ('\n' in value or '\r' in value)


def checkHeaderValue(value):
	"""
	Throws an exception if C{value} is not a valid header value.

	@type value: C{str}
	@param value: HTTP header value
	"""
	if not isinstance(value, str):
		raise TypeError("Header value %r should be a str but found "
			"instance of %r instead" % (value, type(value)))
	if not isValidHeaderValue(value):
		raise ValueError("Header value %r splits into multiple message "
			"headers" % (value,))


def setRawHeadersSafely(headers, name, values):
	"""
	Sets the raw representation of the given header.

	@type name: C{str}
	@param name: The name of the HTTP header to set the values for.

	@type values: C{list}
	@param values: A list of strings each one being a header value of
		the given name.

	@raise TypeError: If C{values} is not a C{list}, or if any item in
		C{values} is not a C{str}.

	@raise ValueError: If any item in C{values} is not a valid HTTP header
		value (i.e. splits into multiple message headers).

	@return: C{None}
	"""
	if not isinstance(values, list):
		raise TypeError("Header entry %r should be list but found "
			"instance of %r instead" % (name, type(values)))
	for value in values:
		checkHeaderValue(value)
	headers.setRawHeaders(name, values)


def addRawHeaderSafely(headers, name, value):
	"""
	Add a new raw value for the given header.

	@type name: C{str}
	@param name: The name of the header for which to set the value.

	@type value: C{str}
	@param value: The value to set for the named header.

	@raise TypeError: If C{value} is not a C{str}.

	@raise ValueError: If C{value} is not a valid HTTP header value (i.e.
		splits into multiple message headers).

	@return: C{None}
	"""
	checkHeaderValue(value)
	headers.addRawHeader(name, value)


try: from refbinder.api import bindRecursive
except ImportError: pass
else: bindRecursive(sys.modules[__name__], _postImportVars)

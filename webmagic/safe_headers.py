"""
Header-setting functions for twisted.web.http_headers.Headers that protect
against response-splitting attacks.
"""

import sys

_postImportVars = vars().keys()


# The functions here are essentially a copy of
# 3770-02-validation-in-Headers-and-server-logging.patch
# from http://twistedmatrix.com/trac/ticket/3770

def isValidHeaderValue(value):
	"""
	Checks whether the input string is a valid HTTP header value (i.e. does
	not cause a message header to split into multiple message headers).

	@type value: C{str}
	@param value: HTTP header value

	@rtype: bool
	@return: Whether the header value is valid.
	"""
	# The common case
	if '\n' not in value:
		return True

	for i, c in enumerate(value):
		if c == '\n':
			# next byte or ""
			next = value[i + 1:i + 2]
			if next not in ("\t", " "):
				return False

	return True


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

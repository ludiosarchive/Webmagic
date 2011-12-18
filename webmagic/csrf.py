"""
Utilities that help protect against CSRF attacks, and a constant-time string
comparison function.
"""

import sys
import base64
import hashlib
import hmac

from zope.interface import implements, Interface

_postImportVars = vars().keys()


def constantTimeCompare(s1, s2):
	"""
	Compare C{s1} and C{s2} for equality, but always take the same amount
	of time when both strings are of the same length.  This is intended to stop
	U{timing attacks<http://rdist.root.org/2009/05/28/timing-attack-in-google-keyczar-library/>}.

	This implementation should do what keyczar does:

	http://code.google.com/p/keyczar/source/browse/trunk/python/src/keyczar/keys.py?r=471#352
	http://rdist.root.org/2010/01/07/timing-independent-array-comparison/

	@param s1: string to compare to s2
	@type s1: C{str}

	@param s2: string to compare to s1
	@type s2: C{str}

	@return: C{True} if strings are equivalent, else C{False}.
	@rtype: C{bool}

	@warning: if C{s1} and C{s2} are of unequal length, the comparison will take
		less time.  An attacker may be able to guess how long the expected
		string is.  To avoid this problem, compare only fixed-length hashes.
	"""
	if isinstance(s1, unicode):
		raise TypeError("First object %r was unicode; expected str" % (s1,))
	if isinstance(s2, unicode):
		raise TypeError("Second object %r was unicode; expected str" % (s2,))

	if len(s1) != len(s2):
		return False
	result = 0
	for x, y in zip(s1, s2):
		result |= ord(x) ^ ord(y)
	return result == 0


# Web browsers are annoying and send the user's cookie to the website
# even when a page on another domain initiates the request. So, this is why
# we need to generate CSRF tokens, output them to webpages, and verify
# CSRF tokens.

# Perhaps this should have a more generic name, like IGenericCorrelator,
# With ICsrfStopper defining the more specific "base64 only" requirement.

class ICsrfStopper(Interface):
	"""
	Interface for CSRF stoppers.

	Note: Callers wrap with maybeDeferred." means that callers wrap this method with
		L{twisted.internet.defer.maybeDeferred}, so you can return a
		Deferred that follows this method's raise/return specification.
	"""

	def makeToken(uuid):
		"""
		@param uuid: The string to make a token for
		@type uuid: C{str}

		@rtype: C{str}
		@return: a bytestring of URL-safe base64 ('-' instead of '+' and '_' instead of '/'),
			or a subset of this alphabet.

		Callers wrap with maybeDeferred.
		"""


	def checkToken(uuidStr, token):
		"""
		@type uuidStr: C{str}
		@param uuidStr: the uuid of the client that claims its CSRF token is C{token}

		@type token: C{str}
		@param token: the CSRF token from the client

		@raise: L{RejectToken} if token is invalid.
		@return: L{None}

		Callers wrap with maybeDeferred.
		"""



class RejectToken(Exception):
	pass



class CsrfStopper(object):
	"""
	An implementation of L{ICsrfStopper} that uses a secret and hmac-sha256
	to make and check tokens. Keeping the secret secret is of paramount
	importance.  If the secret is leaked, anyone can CSRF someone else's
	session.

	The purpose of this is to create a 1:1 mapping of user IDs <-> CSRF tokens.
	The CSRF token should be handed to the client but *not* somewhere where
	it is automatically sent by the browser (whenever browser makes a request
	to your domain).  Putting the CSRF token in a cookie is completely wrong;
	writing the token out to the JavaScript in your HTML might be okay.
	"""
	implements(ICsrfStopper)
	__slots__ = ('_secretString')

	version = '\x00\x00' # one constant for now

	def __init__(self, secretString):
		self._secretString = secretString


	def _hash(self, what):
		# Take the first 128 bits from the 256 bits
		return hmac.new(self._secretString, what, hashlib.sha256).digest()[:16]


	def makeToken(self, uuid):
		"""
		See L{ICsrfStopper.makeToken}
		"""
		digest = self.version + self._hash(uuid)
		return base64.urlsafe_b64encode(digest)


	def checkToken(self, uuidStr, token):
		"""
		See L{ICsrfStopper.isTokenValid}
		"""
		assert isinstance(uuidStr, str)
		try:
			expected = base64.urlsafe_b64decode(token)
		except TypeError:
			raise RejectToken()

		if not constantTimeCompare(expected, self.version + self._hash(uuidStr)):
			raise RejectToken()



try: from refbinder.api import bindRecursive
except ImportError: pass
else: bindRecursive(sys.modules[__name__], _postImportVars)

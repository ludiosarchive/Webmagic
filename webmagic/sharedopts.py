"""
This is for Options that are likely to be shared by multiple twistd plugins.
"""

from __future__ import with_statement

from twisted.python import usage


class WebOptions(usage.Options):
	"""
	An L{Options} that servers with a web component might want to subclass.
	"""
	optParameters	 = [
		["secret", "s", None,
			"A secret string used when generating CSRF tokens. "
			"If you have users, don't change it. Make this 32 bytes or longer."],

		["secretfile", "f", None,
			"A file containing the secret string used when generating CSRF tokens. "
			"See description for --secret."],
	]

	optFlags = [
		["notracebacks", "n", "Don't display tracebacks on the public interfaces."],
	]

	def _checkSecret(self, secret):
		if len(secret) < 32:
			raise usage.UsageError("CSRF secret %r is not long enough. "
				"Make it 32 bytes or longer." % (secret,))
		if len(secret) > 4096:
			raise usage.UsageError("CSRF secret is too long at %d bytes; "
				"it should between 32 bytes and 4096 bytes (inclusive)." % (len(secret),))


	def opt_secret(self, secret):
		self._checkSecret(secret)
		self['secret'] = secret


	def opt_secretfile(self, secretfile):
		with open(secretfile, 'rb') as f:
			secret = f.read().strip()
		self._checkSecret(secret)
		self['secret'] = secret


	def postOptions(self):
		if not self['secret']:
			raise usage.UsageError("A CSRF secret is required (--secret or --secretfile).")

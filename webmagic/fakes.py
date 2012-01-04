"""
Better fakes than those that come with Twisted.
"""

import sys

from zope.interface import implements

from twisted.internet import address, interfaces, task

from twisted.web import server, resource
from twisted.web import http
from twisted.web.test.test_web import DummyRequest as _TwistedDummyRequest
from twisted.test.proto_helpers import StringTransport
#from twisted.internet.test.test_base import FakeReactor as _TwistedFakeReactor

_postImportVars = vars().keys()

# Note: the use of "mock" and "dummy" in this file is totally inconsistent.


class ListLog(list):
	"""
	A list with a .getNew() method that returns items not
	yet returned by previous calls to .getNew().  This is useful when
	writing mock objects that log calls:

		log = ListLog()
		log.append("one")
		log.append("two")

		self.assertEqual(["one", "two"], log.getNew())

		log.append("three")

		self.assertEqual(["three"], log.getNew())
	"""
	__slots__ = ('_lenBeforeLastGetNew',)

	def getNew(self):
		if not hasattr(self, '_lenBeforeLastGetNew'):
			self._lenBeforeLastGetNew = 0

		oldLen = self._lenBeforeLastGetNew
		self._lenBeforeLastGetNew = len(self)

		return self[oldLen:]



class GetNewMixin(object):
	"""
	Deprecated.  Use a L{ListLog} instead.
	"""
	def getNew(self):
		"""
		Returns new log entries. This makes test code a lot less redundant.
		"""
		import warnings
		warnings.warn("fakes.GetNewMixin is deprecated.  "
			"Use a fakes.ListLog instead.")

		if isinstance(self.log, ListLog):
			return self.log.getNew()

		# Support for legacy plain list

		if not hasattr(self, '_returnNext'):
			self._returnNext = 0

		old = self._returnNext
		self._returnNext = len(self.log)

		return self.log[old:]



class DumbLog(GetNewMixin):
	"""
	Deprecated.  Use a L{ListLog} instead.
	"""
	def __init__(self):
		import warnings
		warnings.warn("fakes.DumbLog is deprecated.  "
			"Use a fakes.ListLog instead.")
		self.log = []


	def append(self, item):
		return self.log.append(item)


	def extend(self, items):
		return self.log.extend(items)



class FakeReactor(object):
	# TODO: implements() IReactorCore interface? or whatever
	# addSystemEventTrigger is part of?

	def __init__(self, *args, **kargs):
		self.log = ListLog()


	def getNew(self):
		return self.log.getNew()


	def addSystemEventTrigger(self, *args):
		self.log.append(['addSystemEventTrigger'] + list(args))



class DummyTCPTransport(StringTransport):
	producer = None
	streaming = None

	def __init__(self, *args, **kwargs):
		self.aborted = False
		self.noDelayEnabled = None
		self.keepAliveEnabled = None
		StringTransport.__init__(self, *args, **kwargs)


	# Implement both registerProducer and unregisterProducer because
	# they're only in Twisted >= 9.0
	def registerProducer(self, producer, streaming):
		if self.producer is not None:
			raise RuntimeError("Cannot register two producers")
		self.producer = producer
		self.streaming = streaming


	def unregisterProducer(self):
		"""
		StringTransport does some weird stuff, so do something more
		like the Twisted implementation: don't raise RuntimeError if
		no producer is registered, and don't set self.streaming.
		"""
		self.producer = None


	def setTcpNoDelay(self, enabled):
		self.noDelayEnabled = bool(enabled)


	def getTcpNoDelay(self):
		"""
		Returns the last value of setTcpNoDelay(value), or False, if never
		called.  (Note that this might not match a real transport, if
		NODELAY is enabled by default.)
		"""
		return bool(self.noDelayEnabled)


	def everCalledSetTcpNoDelay(self):
		"""
		Returns True if setTcpNoDelay has ever been called, else False.
		"""
		return self.noDelayEnabled is not None


	def setTcpKeepAlive(self, enabled):
		self.keepAliveEnabled = bool(enabled)


	def getTcpKeepAlive(self):
		"""
		Returns the last value of setTcpKeepAlive(value), or False, if never
		called.  (Note that this might not match a real transport, if
		TCP keepalives are enabled by default.)
		"""
		return bool(self.keepAliveEnabled)


	def everCalledSetTcpKeepAlive(self):
		"""
		Returns True if setTcpKeepAlive has ever been called, else False.
		"""
		return self.keepAliveEnabled is not None


	# StringTransport.abortConnection doesn't exist at this writing
	def abortConnection(self):
		self.unregisterProducer()
		self.aborted = True
		self.disconnecting = True



# copy/paste from twisted.web.test.test_web, but added a setTcpNoDelay
class DummyChannel(object):
	requestIsDone = False

	# TODO: probably use DummyTCPTransport instead of this
	# `class TCP' which has fewer features.
	class TCP(object):
		port = 80
		socket = None
		connectionLostReason = None

		def __init__(self):
			self.noDelayEnabled = False
			self.written = ''
			self.producers = []
			self.paused = 0

		def getPeer(self):
			return address.IPv4Address("TCP", '192.168.1.1', 12344)

		def write(self, bytes):
			assert isinstance(bytes, str)
			self.written += bytes

		def writeSequence(self, iovec):
			for v in iovec:
				self.write(v)

		def getHost(self):
			return address.IPv4Address("TCP", '10.0.0.1', self.port)

		def pauseProducing(self):
			self.paused += 1

		def resumeProducing(self):
			self.paused -= 1

		def registerProducer(self, producer, streaming):
			self.producers.append((producer, streaming))

		def setTcpNoDelay(self, enabled):
			self.noDelayEnabled = bool(enabled)

		def connectionLost(self, reason):
			self.connectionLostReason = reason


	class SSL(TCP):
		implements(interfaces.ISSLTransport)


	def __init__(self, clock=None):
		if clock is None:
			clock = task.Clock()
		try:
			self.site = server.Site(resource.Resource(), clock=clock)
		except TypeError:
			self.site = server.Site(resource.Resource())
		self.transport = self.TCP()


	def requestDone(self, request):
		self.requestIsDone = True



class DummyRequest(_TwistedDummyRequest):

	def __init__(self, *args, **kwargs):
		_TwistedDummyRequest.__init__(self, *args, **kwargs)

		self.startedWriting = False
		self._disconnected = False

		# This is needed because _BaseHTTPTransport does
		#     self.request.channel.transport.setTcpNoDelay(True)
		self.channel = DummyChannel()

		self.received_cookies = {}


	def write(self, data):
		self.startedWriting = True
		_TwistedDummyRequest.write(self, data)


	def processingFailed(self, reason):
		self._disconnected = True
		_TwistedDummyRequest.processingFailed(self, reason)


	def setHeader(self, name, value):
		"""
		L{twisted.web.test.test_web.DummyRequest} does strange stuff in
		C{setHeader} -- it modifies self.outgoingHeaders, which is not close
		enough to reality.
		"""
		self.responseHeaders.setRawHeaders(name, [value])


	def redirect(self, url):
		"""
		Utility function that does a redirect.

		The request should have finish() called after this.
		"""
		self.setResponseCode(http.FOUND)
		self.setHeader("location", url)


	def isSecure(self):
		return False


	def getCookie(self, name):
		return self.received_cookies.get(name)



class MockProducer(object):
	resumed = False
	stopped = False
	paused = False

	def __init__(self):
		self.log = ListLog()


	def getNew(self):
		return self.log.getNew()


	def resumeProducing(self):
		self.log.append(['resumeProducing'])
		self.resumed = True
		self.paused = False


	def pauseProducing(self):
		self.log.append(['pauseProducing'])
		self.paused = True


	def stopProducing(self):
		self.log.append(['stopProducing'])
		self.stopped = True



try: from refbinder.api import bindRecursive
except ImportError: pass
else: bindRecursive(sys.modules[__name__], _postImportVars)

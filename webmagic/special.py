"""
Special resources used for testing browser behavior
"""

from twisted.web import resource, server

from webmagic.untwist import setNoCacheNoStoreHeaders


def stringToWaitTime(s):
	try:
		waitTime = int(s)
	except ValueError:
		waitTime = 30
	else:
		if not 0 <= waitTime <= 60*10:
			waitTime = 30

	return waitTime


def requestToWaitTime(request):
	try:
		waitStr = request.args['wait'][0]
	except (KeyError, IndexError):
		waitTime = 30
	else:
		waitTime = stringToWaitTime(waitStr)
	return waitTime


class WaitResource(resource.Resource):
	"""
	A resource that waits for the number of seconds specified in the body.
	This is used for a Chrome bug test page hosted on http://ludios.net/
	"""
	isLeaf = True

	def __init__(self, clock):
		resource.Resource.__init__(self)
		self._clock = clock


	def render_GET(self, request):
		"""
		For GET requests, return a 1x1 GIF in N seconds, where N is
		determined by the ?wait= parameter in the URL.
		"""
		waitTime = requestToWaitTime(request)

		blankGif = (
			'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00'
			'\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')

		setNoCacheNoStoreHeaders(request)
		request.responseHeaders.setRawHeaders('content-type', ['image/gif'])
		request.responseHeaders.setRawHeaders('access-control-allow-origin', ['*'])

		def writeAndFinish():
			request.write(blankGif)
			request.finish()

		dc = self._clock.callLater(waitTime, writeAndFinish)

		d = request.notifyFinish()
		d.addErrback(lambda _: dc.cancel())

		return server.NOT_DONE_YET


	def render_POST(self, request):
		"""
		For POST requests, return a psuedo-HTML file in N seconds,
		where N is determined by
		"""
		waitTime = requestToWaitTime(request)

		setNoCacheNoStoreHeaders(request)
		request.responseHeaders.setRawHeaders('access-control-allow-origin', ['*'])

		def writeAndFinish():
			request.write("// Done after %d seconds." % (waitTime,))
			request.finish()

		dc = self._clock.callLater(waitTime, writeAndFinish)

		d = request.notifyFinish()
		d.addErrback(lambda _: dc.cancel())

		return server.NOT_DONE_YET

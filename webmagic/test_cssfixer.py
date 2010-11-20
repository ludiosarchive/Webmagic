from twisted.trial import unittest

from webmagic.cssfixer import ReferencedFile


class TestReferencedFile(unittest.TestCase):

	def test_attrs(self):
		rf = ReferencedFile('nonexistent', 'abcd')
		self.assertEqual(rf.path, 'nonexistent')
		self.assertEqual(rf.lasthash, 'abcd')


	def test_repr(self):
		rf = ReferencedFile('nonexistent', 'abcd')
		self.assertEqual("ReferencedFile('nonexistent', 'abcd')", repr(rf))

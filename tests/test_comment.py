import io
import json
import unittest
from promptgit.github_comment import publish

class CommentTests(unittest.TestCase):
    def test_contract_without_sending(self):
        calls=[]
        def fake(request, timeout):
            calls.append(request)
            self.assertEqual(timeout,20)
            return io.StringIO('{"html_url":"https://example.invalid/comment/1"}')
        event={'number':7,'pull_request':{'head':{'repo':{'full_name':'owner/repo'}}}}
        url=publish(event,'owner/repo','fake-test-token','fixed summary',fake)
        self.assertEqual(url,'https://example.invalid/comment/1')
        self.assertEqual(calls[0].full_url,'https://api.github.com/repos/owner/repo/issues/7/comments')
        self.assertEqual(calls[0].method,'POST')
        self.assertEqual(json.loads(calls[0].data),{'body':'fixed summary'})

    def test_reject_before_network(self):
        def forbidden(*a, **k): self.fail('network should not be used')
        for event,repo,token in [({},'owner/repo','token'),
            ({'number':1,'pull_request':{'head':{'repo':{'full_name':'fork/repo'}}}},'owner/repo','token'),
            ({},'../bad','token')]:
            with self.assertRaises(ValueError): publish(event,repo,token,'body',forbidden)

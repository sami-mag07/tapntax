"""The service guards: a token when it is reachable, no wildcard CORS, a body limit."""

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer


def serve(env: dict):
    """Import the server fresh with this environment, on a free port."""
    for k, v in env.items():
        os.environ[k] = v
    import importlib

    from tapntax import server as mod
    mod = importlib.reload(mod)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_port}", mod


def call(url, body=None, token=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read() or b"{}"), dict(r.headers)


class Guards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, cls.base, cls.mod = serve({
            "TAPNTAX_TOKEN": "test-token-please-ignore",
            "TAPNTAX_STATE": "/tmp/tapntax-test-state",
            "TAPNTAX_ORIGIN": "",
        })

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        for k in ("TAPNTAX_TOKEN", "TAPNTAX_STATE", "TAPNTAX_ORIGIN"):
            os.environ.pop(k, None)

    def test_entries_need_the_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            call(f"{self.base}/v1/entries")
        self.assertEqual(e.exception.code, 401)

    def test_a_wrong_token_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            call(f"{self.base}/v1/entries", token="wrong")
        self.assertEqual(e.exception.code, 401)

    def test_the_right_token_works(self):
        status, body, _ = call(f"{self.base}/v1/entries", token="test-token-please-ignore")
        self.assertEqual(status, 200)
        self.assertIn("entries", body)

    def test_health_stays_open_for_probes(self):
        self.assertEqual(call(f"{self.base}/v1/health")[0], 200)

    def test_no_wildcard_cors_by_default(self):
        _, _, headers = call(f"{self.base}/v1/health")
        self.assertNotEqual(headers.get("Access-Control-Allow-Origin"), "*")

    def test_posting_a_payment_needs_the_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            call(f"{self.base}/v1/payment", {"merchant": "ADOBE", "amount": 9.99})
        self.assertEqual(e.exception.code, 401)

    def test_a_payment_with_the_token_is_decided(self):
        status, body, _ = call(f"{self.base}/v1/payment",
                               {"merchant": "ADOBE SYSTEMS GMBH", "amount": 59.49,
                                "card": "Business Visa 4821"},
                               token="test-token-please-ignore")
        self.assertEqual(status, 200)
        self.assertIn(body["decision"]["action"], ("ask", "file", "ignore"))
        self.assertTrue(body["decision"]["reason"])


if __name__ == "__main__":
    unittest.main()

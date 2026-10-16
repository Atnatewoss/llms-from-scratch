"""Tests for the FastAPI surface: liveness, RPC mount, CORS wiring.

No HTTP client is used, so the app object is inspected directly instead of
standing up a server (the RPC surface itself is covered by `main.reply` ->
`core.rule.respond`, tested in `tests.test_rules`).
"""

import unittest

from main import app, health


class TestApiSurface(unittest.TestCase):
    def test_health(self):
        self.assertEqual(health(), {"status": "ok"})

    def test_health_route_exists(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/health", paths)

    def test_rpc_endpoint_is_mounted(self):
        paths = {getattr(route, "path", None) for route in app.routes}
        self.assertIn("/rpc", paths, "pyRPC must be mounted for the web client")

    def test_cors_allows_the_web_origin_by_default(self):
        middleware = [
            m for m in app.user_middleware if getattr(m, "cls", None).__name__ == "CORSMiddleware"
        ]
        self.assertTrue(middleware, "CORSMiddleware should be installed")
        self.assertIn("http://localhost:3000", middleware[0].kwargs["allow_origins"])


if __name__ == "__main__":
    unittest.main()

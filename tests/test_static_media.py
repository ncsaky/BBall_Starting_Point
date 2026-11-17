"""Browser-friendly local media delivery without weakening HTTP boundaries."""

import http.client
from email.message import Message
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from nba_gm_data import app_server


class StaticMediaTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.body = bytes(range(256)) * 1000
        (self.root / "movie.mp4").write_bytes(self.body)
        (self.root / "index.html").write_text("hello")
        gui = patch.object(app_server, "GUI_DIR", self.root)
        gui.start()
        self.addCleanup(gui.stop)
        with patch.object(app_server, "load_app_canonical", return_value={"teams": []}):
            self.server = app_server.make_gui_server(root=self.root, save_dir=self.root / "saves", port=0)
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        def stop():
            self.server.shutdown()
            self.server.server_close()
            worker.join(5)
        self.addCleanup(stop)

    def request(self, method="GET", path="/movie.mp4", headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_full_video_and_head(self):
        status, headers, body = self.request()
        self.assertEqual((status, body), (200, self.body))
        self.assertEqual(headers["Content-Type"], "video/mp4")
        self.assertEqual(headers["Accept-Ranges"], "bytes")
        status, headers, body = self.request("HEAD")
        self.assertEqual((status, body), (200, b""))
        self.assertEqual(int(headers["Content-Length"]), len(self.body))

    def test_conditional_requests_reuse_only_unchanged_static_files(self):
        status, headers, body = self.request(path="/")
        self.assertEqual((status, body), (200, b"hello"))
        self.assertEqual(headers["Cache-Control"], "no-cache")
        etag = headers["ETag"]
        status, headers, body = self.request(path="/", headers={"If-None-Match": etag})
        self.assertEqual((status, body), (304, b""))
        (self.root / "index.html").write_text("updated game")
        status, headers, body = self.request(path="/", headers={"If-None-Match": etag})
        self.assertEqual((status, body), (200, b"updated game"))
        self.assertNotEqual(headers["ETag"], etag)

    def test_images_are_cacheable_and_range_requests_still_return_content(self):
        (self.root / "assets").mkdir()
        (self.root / "assets" / "headshot.png").write_bytes(b"image")
        status, headers, body = self.request(path="/assets/headshot.png")
        self.assertEqual((status, body), (200, b"image"))
        self.assertEqual(headers["Cache-Control"], "public, max-age=86400")
        _, headers, _ = self.request()
        status, _, body = self.request(headers={
            "If-None-Match": headers["ETag"], "Range": "bytes=0-1",
        })
        self.assertEqual((status, body), (206, self.body[:2]))

    def test_bounded_open_and_suffix_ranges(self):
        for value, start, end in [("bytes=0-1", 0, 1), ("bytes=100-199", 100, 199),
                                  ("bytes=255990-", 255990, 255999), ("bytes=-10", 255990, 255999),
                                  ("bytes=255990-999999", 255990, 255999)]:
            with self.subTest(value=value):
                status, headers, body = self.request(headers={"Range": value})
                self.assertEqual((status, body), (206, self.body[start:end + 1]))
                self.assertEqual(headers["Content-Range"], f"bytes {start}-{end}/{len(self.body)}")

    def test_invalid_ranges_are_rejected_without_reading_media(self):
        for value in ["bytes=999999-", "bytes=10-2", "bytes=-0", "bytes=-", "bytes=0-1,4-5", "garbage", "bytes=" + "9" * 5000 + "-"]:
            with self.subTest(value=value[:40]):
                status, headers, body = self.request(headers={"Range": value})
                self.assertEqual((status, body), (416, b""))
                self.assertEqual(headers["Content-Range"], f"bytes */{len(self.body)}")

    def test_static_and_request_boundaries_remain_intact(self):
        self.assertEqual(self.request(path="/")[2], b"hello")
        self.assertEqual(self.request(path="/../outside.mp4")[0], 404)
        self.assertEqual(self.request(headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.request("HEAD", headers={"Host": "evil.example"})[0], 403)

    def test_cancelled_media_requests_stop_quietly_but_other_io_errors_surface(self):
        for error in (BrokenPipeError("navigated away"), ConnectionResetError("closed browser"), OSError("unexpected failure")):
            with self.subTest(error=type(error).__name__):
                handler = SimpleNamespace(headers=Message(), wfile=Mock(), send_response=Mock(),
                                          send_header=Mock(), end_headers=Mock(), send_error=Mock())
                handler.wfile.write.side_effect = error
                if isinstance(error, (BrokenPipeError, ConnectionResetError)):
                    app_server.GuiRequestHandler.serve_static(handler, "/movie.mp4")
                    self.assertEqual(handler.wfile.write.call_count, 1)
                    handler.send_error.assert_not_called()
                else:
                    with self.assertRaises(OSError):
                        app_server.GuiRequestHandler.serve_static(handler, "/movie.mp4")


if __name__ == "__main__":
    unittest.main()

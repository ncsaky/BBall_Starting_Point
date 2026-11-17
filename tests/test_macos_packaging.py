"""Regression for startup independence discovered in packaged-app testing."""

from unittest.mock import patch

from nba_gm_data.app_server import make_gui_server


def test_loopback_startup_does_not_resolve_dns(tmp_path):
    with patch("socket.getfqdn", side_effect=AssertionError("Unexpected DNS lookup")):
        server = make_gui_server(save_dir=tmp_path / "isolated-saves", port=0)
        try:
            assert server.server_address[0] == "127.0.0.1"
            assert server.server_address[1] > 0
            assert server.server_name == "localhost"
        finally:
            server.server_close()

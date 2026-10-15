"""Disposable local server proof; never connects to hosted/customer storage."""
import http.client
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest


@pytest.mark.parametrize("keepalive, reusable", [(3, False), (65, True)])
def test_uvicorn_worker_connection_survives_proxy_reuse_window(tmp_path: Path, keepalive: int, reusable: bool) -> None:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    env = {**os.environ, "DATABASE_URL": "", "PERFORMANCE_AI_STORAGE_DIR": str(tmp_path / "storage"),
           "CIVORA_AI_PROVIDER": "none", "CIVORA_IMAGE_PROVIDER": "none", "CIVORA_PRODUCT_MODE": "private_alpha"}
    process = subprocess.Popen([
        sys.executable, "-m", "gunicorn", "backend.api.app:app", "--bind", f"127.0.0.1:{port}",
        "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker", "--keep-alive", str(keepalive),
    ], cwd=Path(__file__).resolve().parents[1], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        deadline = time.monotonic() + 15
        while True:
            assert process.poll() is None, "Disposable server exited before readiness"
            try:
                connection.request("GET", "/api/health")
                response = connection.getresponse()
                assert response.status == 200
                response.read()
                break
            except (ConnectionError, http.client.HTTPException):
                connection.close()
                if time.monotonic() > deadline:
                    pytest.fail("Disposable server readiness deadline expired")
                time.sleep(0.05)
        original_socket = connection.sock
        assert original_socket is not None
        time.sleep(4.2)
        if reusable:
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            assert response.status == 200
            response.read()
            assert connection.sock is original_socket, "Must reuse the existing TCP connection, not reconnect"
        else:
            with pytest.raises((ConnectionError, http.client.RemoteDisconnected)):
                connection.request("GET", "/api/health")
                connection.getresponse()
    finally:
        connection.close()
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

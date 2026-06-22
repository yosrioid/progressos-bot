import asyncio
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field

import pytest

from progressos_bot.webhook import (
    TelegramWebhookServer,
    WebhookServerConfig,
    run_webhook_application,
)


@dataclass
class FakeBot:
    webhook_url: str | None = None
    webhook_secret: str | None = None

    async def set_webhook(self, *, url: str, secret_token: str | None = None) -> None:
        self.webhook_url = url
        self.webhook_secret = secret_token


@dataclass
class FakeApplication:
    running: bool = True
    bot: FakeBot = field(default_factory=FakeBot)
    processed_updates: int = 0
    initialized: bool = False
    started: bool = False
    stopped: bool = False
    shut_down: bool = False

    async def initialize(self) -> None:
        self.initialized = True

    async def start(self) -> None:
        self.started = True
        self.running = True

    async def stop(self) -> None:
        self.stopped = True
        self.running = False

    async def shutdown(self) -> None:
        self.shut_down = True

    async def process_update(self, update: object) -> None:
        del update
        self.processed_updates += 1


@dataclass
class FakeServer:
    started: bool = False
    shutdown_called: bool = False
    cancelled: bool = False

    async def serve_until_stopped(self) -> None:
        self.started = True
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    def shutdown(self) -> None:
        self.shutdown_called = True


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _wait_for_server(url: str) -> None:
    for _ in range(50):
        try:
            await asyncio.to_thread(_read_json, url)
            return
        except OSError:
            await asyncio.sleep(0.02)
    pytest.fail("Webhook server did not start")


def _read_json(url: str) -> tuple[int, dict[str, str]]:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _post_json(
    url: str,
    payload: dict[str, object],
    *,
    secret: str | None = None,
) -> tuple[int, dict[str, str]]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if secret is not None:
        request.add_header("X-Telegram-Bot-Api-Secret-Token", secret)
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


async def _async_read_json(url: str) -> tuple[int, dict[str, str]]:
    return await asyncio.to_thread(_read_json, url)


async def _async_post_json(
    url: str,
    payload: dict[str, object],
    *,
    secret: str | None = None,
) -> tuple[int, dict[str, str]]:
    return await asyncio.to_thread(_post_json, url, payload, secret=secret)


@pytest.mark.asyncio
async def test_webhook_server_health_and_readiness() -> None:
    port = _free_port()
    server = TelegramWebhookServer(
        config=WebhookServerConfig(
            host="127.0.0.1",
            port=port,
            webhook_path="/telegram/webhook",
            health_path="/health",
            readiness_path="/ready",
        ),
        application=FakeApplication(running=True),
    )
    task = asyncio.create_task(server.serve_until_stopped())
    try:
        await _wait_for_server(f"http://127.0.0.1:{port}/health")

        assert await _async_read_json(f"http://127.0.0.1:{port}/health") == (
            200,
            {"status": "ok"},
        )
        assert await _async_read_json(f"http://127.0.0.1:{port}/ready") == (
            200,
            {"status": "ready"},
        )
    finally:
        server.shutdown()
        await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_webhook_server_rejects_invalid_secret() -> None:
    port = _free_port()
    app = FakeApplication(running=True)
    server = TelegramWebhookServer(
        config=WebhookServerConfig(
            host="127.0.0.1",
            port=port,
            webhook_path="/telegram/webhook",
            health_path="/health",
            readiness_path="/ready",
            webhook_secret="expected-secret",
        ),
        application=app,
    )
    task = asyncio.create_task(server.serve_until_stopped())
    try:
        await _wait_for_server(f"http://127.0.0.1:{port}/health")

        assert await _async_post_json(
            f"http://127.0.0.1:{port}/telegram/webhook",
            {"update_id": 1},
            secret="wrong-secret",
        ) == (403, {"error": "forbidden"})
        assert app.processed_updates == 0
    finally:
        server.shutdown()
        await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_webhook_server_accepts_valid_secret() -> None:
    port = _free_port()
    app = FakeApplication(running=True)
    server = TelegramWebhookServer(
        config=WebhookServerConfig(
            host="127.0.0.1",
            port=port,
            webhook_path="/telegram/webhook",
            health_path="/health",
            readiness_path="/ready",
            webhook_secret="expected-secret",
        ),
        application=app,
    )
    task = asyncio.create_task(server.serve_until_stopped())
    try:
        await _wait_for_server(f"http://127.0.0.1:{port}/health")

        assert await _async_post_json(
            f"http://127.0.0.1:{port}/telegram/webhook",
            {"update_id": 1},
            secret="expected-secret",
        ) == (200, {"status": "accepted"})
        assert app.processed_updates == 1
    finally:
        server.shutdown()
        await asyncio.wait_for(task, timeout=2)


@pytest.mark.asyncio
async def test_run_webhook_application_stops_cleanly() -> None:
    app = FakeApplication(running=False)
    server = FakeServer()

    async def stop_soon() -> None:
        await asyncio.sleep(0.01)

    await run_webhook_application(
        application=app,
        server=server,
        webhook_url="https://example.com/telegram/webhook",
        webhook_secret="secret-token",
        stop_event_factory=stop_soon,
    )

    assert app.initialized
    assert app.started
    assert app.stopped
    assert app.shut_down
    assert app.bot.webhook_url == "https://example.com/telegram/webhook"
    assert app.bot.webhook_secret == "secret-token"
    assert server.started
    assert server.shutdown_called
    assert server.cancelled

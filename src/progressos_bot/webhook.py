import asyncio
import json
import logging
import signal
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from telegram import Update

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebhookServerConfig:
    host: str
    port: int
    webhook_path: str
    health_path: str
    readiness_path: str
    webhook_secret: str = ""


class TelegramWebhookServer:
    def __init__(self, *, config: WebhookServerConfig, application: Any) -> None:
        self._config = config
        self._application = application
        self._server: ThreadingHTTPServer | None = None

    async def serve_until_stopped(self) -> None:
        loop = asyncio.get_running_loop()
        handler = self._make_handler(loop)
        self._server = ThreadingHTTPServer((self._config.host, self._config.port), handler)
        self._server.daemon_threads = True
        try:
            logger.info(
                "Starting webhook server",
                extra={
                    "webhook_host": self._config.host,
                    "webhook_port": self._config.port,
                    "webhook_path": self._config.webhook_path,
                },
            )
            serve_future = loop.run_in_executor(None, self._server.serve_forever)
            try:
                await asyncio.shield(serve_future)
            except asyncio.CancelledError:
                self.shutdown()
                await serve_future
                raise
        finally:
            self._server.server_close()
            self._server = None

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.shutdown()

    def _make_handler(self, loop: asyncio.AbstractEventLoop) -> type[BaseHTTPRequestHandler]:
        config = self._config
        application = self._application

        class Handler(BaseHTTPRequestHandler):
            server_version = "ProgressOSWebhook/1.0"

            def log_message(self, format: str, *args: object) -> None:
                logger.info("Webhook HTTP request", extra={"http_message": format % args})

            def do_GET(self) -> None:
                if self.path == config.health_path:
                    self._write_json(HTTPStatus.OK, {"status": "ok"})
                    return
                if self.path == config.readiness_path:
                    is_ready = bool(getattr(application, "running", False))
                    status = HTTPStatus.OK if is_ready else HTTPStatus.SERVICE_UNAVAILABLE
                    body_status = "ready" if is_ready else "starting"
                    self._write_json(status, {"status": body_status})
                    return
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

            def do_POST(self) -> None:
                if self.path != config.webhook_path:
                    self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                    return
                if not self._has_valid_secret():
                    self._write_json(HTTPStatus.FORBIDDEN, {"error": "forbidden"})
                    return

                content_length = self.headers.get("Content-Length")
                if content_length is None:
                    self._write_json(
                        HTTPStatus.LENGTH_REQUIRED,
                        {"error": "missing_content_length"},
                    )
                    return

                try:
                    body = self.rfile.read(int(content_length))
                    payload = json.loads(body)
                except ValueError:
                    self._write_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
                    return

                try:
                    update = Update.de_json(payload, application.bot)
                    future = asyncio.run_coroutine_threadsafe(
                        application.process_update(update),
                        loop,
                    )
                    future.result(timeout=30)
                except Exception:
                    logger.exception("Failed to process Telegram webhook update")
                    self._write_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"error": "processing_failed"},
                    )
                    return

                self._write_json(HTTPStatus.OK, {"status": "accepted"})

            def _has_valid_secret(self) -> bool:
                if not config.webhook_secret:
                    return True
                return (
                    self.headers.get("X-Telegram-Bot-Api-Secret-Token")
                    == config.webhook_secret
                )

            def _write_json(self, status: HTTPStatus, payload: dict[str, str]) -> None:
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


async def run_webhook_application(
    *,
    application: Any,
    server: TelegramWebhookServer,
    webhook_url: str | None,
    webhook_secret: str,
    stop_event_factory: Callable[[], Awaitable[None]] | None = None,
) -> None:
    await application.initialize()
    try:
        await application.start()
        try:
            if webhook_url is not None:
                await application.bot.set_webhook(
                    url=webhook_url,
                    secret_token=webhook_secret or None,
                )

            if stop_event_factory is None:
                stop_event_factory = wait_for_shutdown_signal

            server_task: asyncio.Future[None] = asyncio.create_task(
                server.serve_until_stopped()
            )
            stop_task: asyncio.Future[None] = asyncio.ensure_future(stop_event_factory())
            done, pending = await asyncio.wait(
                {server_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            server.shutdown()
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()
        finally:
            server.shutdown()
            await application.stop()
    finally:
        await application.shutdown()


async def wait_for_shutdown_signal() -> None:
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    registered_signals: list[signal.Signals] = []

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except (NotImplementedError, RuntimeError):
            logger.debug(
                "Signal handler registration is unavailable",
                extra={"signal_name": signum.name},
            )
        else:
            registered_signals.append(signum)

    try:
        await stop_event.wait()
    finally:
        for signum in registered_signals:
            loop.remove_signal_handler(signum)

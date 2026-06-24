from collections.abc import Collection
from dataclasses import dataclass


@dataclass(frozen=True)
class VersionInfo:
    app_name: str
    app_version: str
    app_env: str
    run_mode: str
    log_format: str

    def to_user_message(self) -> str:
        return "\n".join(
            [
                f"{self.app_name} {self.app_version}",
                f"Env: {self.app_env}",
                f"Mode: {self.run_mode}",
                f"Log: {self.log_format}",
            ]
        )


@dataclass(frozen=True)
class ConfigurationDiagnostics:
    app_env: str
    run_mode: str
    log_format: str
    capture_enabled_intents: Collection[str]
    capture_pre_parser_guard_mode: str
    pending_store_enabled: bool
    retry_queue_enabled: bool
    allowlist_configured: bool
    user_map_configured: bool
    webhook_secret_configured: bool

    def to_user_message(self) -> str:
        return "\n".join(
            [
                "Diagnostics:",
                f"Env: {self.app_env}",
                f"Mode: {self.run_mode}",
                f"Log: {self.log_format}",
                f"Capture intents: {self._format_collection(self.capture_enabled_intents)}",
                f"Pre-parser guard: {self.capture_pre_parser_guard_mode}",
                f"Pending store: {self._format_bool(self.pending_store_enabled)}",
                f"Retry queue: {self._format_bool(self.retry_queue_enabled)}",
                f"Allowlist: {self._format_bool(self.allowlist_configured)}",
                f"User map: {self._format_bool(self.user_map_configured)}",
                f"Webhook secret: {self._format_bool(self.webhook_secret_configured)}",
            ]
        )

    @staticmethod
    def _format_bool(value: bool) -> str:
        return "configured" if value else "not configured"

    @staticmethod
    def _format_collection(values: Collection[str]) -> str:
        if not values:
            return "none"
        return ", ".join(sorted(values))


class AdminInfoService:
    def __init__(
        self,
        version_info: VersionInfo,
        diagnostics: ConfigurationDiagnostics,
    ) -> None:
        self._version_info = version_info
        self._diagnostics = diagnostics

    def version(self) -> VersionInfo:
        return self._version_info

    def diagnostics(self) -> ConfigurationDiagnostics:
        return self._diagnostics

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


class AdminInfoService:
    def __init__(self, version_info: VersionInfo) -> None:
        self._version_info = version_info

    def version(self) -> VersionInfo:
        return self._version_info

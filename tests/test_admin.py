from progressos_bot.core.admin import (
    AdminInfoService,
    ConfigurationDiagnostics,
    VersionInfo,
)


def make_diagnostics() -> ConfigurationDiagnostics:
    return ConfigurationDiagnostics(
        app_env="local",
        run_mode="polling",
        log_format="text",
        capture_enabled_intents={"create_task", "log_work"},
        pending_store_enabled=False,
        retry_queue_enabled=True,
        allowlist_configured=True,
        user_map_configured=True,
        webhook_secret_configured=False,
    )


def test_version_info_user_message_is_secret_safe() -> None:
    info = VersionInfo(
        app_name="progressos-bot",
        app_version="0.1.0",
        app_env="production",
        run_mode="webhook",
        log_format="json",
    )

    assert info.to_user_message() == "\n".join(
        [
            "progressos-bot 0.1.0",
            "Env: production",
            "Mode: webhook",
            "Log: json",
        ]
    )


def test_admin_info_service_returns_version_info() -> None:
    info = VersionInfo(
        app_name="progressos-bot",
        app_version="0.1.0",
        app_env="local",
        run_mode="polling",
        log_format="text",
    )
    service = AdminInfoService(version_info=info, diagnostics=make_diagnostics())

    assert service.version() == info


def test_configuration_diagnostics_user_message_is_secret_safe() -> None:
    diagnostics = ConfigurationDiagnostics(
        app_env="production",
        run_mode="webhook",
        log_format="json",
        capture_enabled_intents={"create_task", "create_blocker"},
        pending_store_enabled=True,
        retry_queue_enabled=True,
        allowlist_configured=True,
        user_map_configured=True,
        webhook_secret_configured=True,
    )

    message = diagnostics.to_user_message()

    assert message == "\n".join(
        [
            "Diagnostics:",
            "Env: production",
            "Mode: webhook",
            "Log: json",
            "Capture intents: create_blocker, create_task",
            "Pending store: configured",
            "Retry queue: configured",
            "Allowlist: configured",
            "User map: configured",
            "Webhook secret: configured",
        ]
    )
    assert "token" not in message.lower()
    assert "change-me" not in message.lower()


def test_admin_info_service_returns_diagnostics() -> None:
    diagnostics = make_diagnostics()
    service = AdminInfoService(
        version_info=VersionInfo(
            app_name="progressos-bot",
            app_version="0.1.0",
            app_env="local",
            run_mode="polling",
            log_format="text",
        ),
        diagnostics=diagnostics,
    )

    assert service.diagnostics() == diagnostics

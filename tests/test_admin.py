from progressos_bot.core.admin import AdminInfoService, VersionInfo


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
    service = AdminInfoService(info)

    assert service.version() == info

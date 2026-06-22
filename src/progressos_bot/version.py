from importlib.metadata import PackageNotFoundError, version


def get_package_version() -> str:
    try:
        return version("progressos-bot")
    except PackageNotFoundError:
        return "0.0.0+local"

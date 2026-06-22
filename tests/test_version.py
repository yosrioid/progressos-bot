from importlib.metadata import PackageNotFoundError

from progressos_bot import version as version_module


def test_get_package_version_returns_installed_version(monkeypatch) -> None:
    monkeypatch.setattr(version_module, "version", lambda package_name: "1.2.3")

    assert version_module.get_package_version() == "1.2.3"


def test_get_package_version_falls_back_for_uninstalled_package(monkeypatch) -> None:
    def raise_package_not_found(package_name: str) -> str:
        del package_name
        raise PackageNotFoundError

    monkeypatch.setattr(version_module, "version", raise_package_not_found)

    assert version_module.get_package_version() == "0.0.0+local"

"""Fixtures that build a real podpack site with the notebooks app installed."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from podpack import create_app

SiteFactory = Callable[..., Flask]

HOST_CONFIG: dict[str, Any] = {
    "site": {"name": "test site", "environment": "test", "apps": ["podpack_notebooks"]},
}


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SiteFactory:
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")
    # Required since login became core: flask-security keys password hashes on
    # it and podpack refuses to boot without it. This app has no login of its
    # own and needs it anyway, because every podpack site has one.
    monkeypatch.setenv("SECURITY_PASSWORD_SALT", "test-password-salt")

    def _build(**overrides: Any) -> Flask:
        config = {**HOST_CONFIG, **overrides.pop("host_config", {})}
        return create_app(
            host_config=config,
            data_root=tmp_path / "data",
            log_root=tmp_path / "logs",
            **overrides,
        )

    return _build

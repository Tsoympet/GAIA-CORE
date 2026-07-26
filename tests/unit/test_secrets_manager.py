import pytest

from gaia.security import Permission, PermissionManager, SecretsManager


def test_secret_reads_require_explicit_human_approval() -> None:
    permissions = PermissionManager()
    secrets = SecretsManager(permissions)
    secrets.set("GAIA_API_KEY", "secret-value")

    with pytest.raises(PermissionError, match="no matching allow rule"):
        secrets.get("GAIA_API_KEY")

    permissions.grant(
        Permission.SECRET_READ,
        "GAIA_API_KEY",
        reason="operator-approved secret read",
        human_approved=True,
    )

    assert secrets.get("GAIA_API_KEY") == "secret-value"


def test_secret_listing_is_redacted() -> None:
    secrets = SecretsManager(PermissionManager())
    secrets.set("TOKEN", "abcdefgh")

    listed = secrets.list_redacted()

    assert listed == [
        {
            "name": "TOKEN",
            "value": "ab****gh",
            "source": "memory",
        }
    ]


def test_secret_name_must_not_be_empty() -> None:
    secrets = SecretsManager(PermissionManager())

    with pytest.raises(ValueError, match="secret name must not be empty"):
        secrets.set("   ", "value")

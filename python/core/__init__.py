"""FlashPilot core package."""

# APP_VERSION is the *installed* version — what the user downloaded.
# When installed via pip/deb, derive it from package metadata so the
# deb version (pyproject.toml) is the single source of truth. When
# running from source (no installed distribution), fall back to the
# dev constant.
try:
    from importlib.metadata import version as _pkg_version  # Python 3.8+

    try:
        APP_VERSION = _pkg_version("flashpilot")
    except Exception:
        APP_VERSION = "1.2.1-beta.1"
except Exception:
    APP_VERSION = "1.2.1-beta.1"

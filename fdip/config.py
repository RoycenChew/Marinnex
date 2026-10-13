"""Settings, read once from the environment or a git-ignored `.env`.

Two rules shape this module. Secrets are never echoed: `__repr__` is not
customised because nothing here is printed, and the key accessors return the
value rather than storing it anywhere else. And a missing secret is a startup
failure in live mode rather than a silent fallback, because a default pepper
would make every stored key hash forgeable.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

PROVIDER_MODES = ("live", "recorded", "mock")


def _load_dotenv(path: Path) -> None:
    """Populate `os.environ` from a `.env` file without overwriting it.

    Hand-rolled rather than pulled from a library because the format needed here
    is three lines of parsing and the environment must win: a value exported in
    the shell is the operator's explicit choice.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_url: str
    provider_mode: str
    model: str
    extract_thinking: str
    """The override, when `FDIP_EXTRACT_THINKING` is set explicitly. Empty means
    the per-route defaults below apply."""
    extract_thinking_digital: str
    extract_thinking_scan: str
    scan_auto_accept: bool
    key_pepper: str
    session_secret: str
    monthly_ceiling_usd: float
    cors_origins: tuple[str, ...]
    dev_seed: bool
    environment: str = "development"
    """`production` tightens several defaults that are deliberately loose
    locally. See `is_production`."""
    allow_registration: bool = True
    """False is the launch posture: accounts are created by invitation, and
    `/auth/register` answers 403 rather than pretending not to exist."""
    login_attempts_per_minute: int = 10
    uploads_per_minute: int = 30
    max_upload_bytes: int = 20 * 1024 * 1024
    max_pages: int = 25
    sandbox_timeout_seconds: float = 60.0
    model_timeout_seconds: float = 90.0
    job_lease_seconds: float = 300.0
    rate_limit_per_minute: int = 60
    extract_max_tokens: int = 16000
    deepseek_api_key: str = field(default="", repr=False)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def thinking_for_route(self, route: str) -> str:
        """`on` for a text layer, `repair` for a scan, unless overridden.

        Route A is the text layer; B is OCR and C is page images, and both of those
        are documents the model has to reason about rather than read.
        """
        return (self.extract_thinking_digital if route == "A"
                else self.extract_thinking_scan)

    @property
    def blob_dir(self) -> Path:
        return self.data_dir / "blobs"

    @property
    def checkpoint_path(self) -> Path:
        return self.data_dir / "checkpoints.sqlite"

    @property
    def llm_cache_path(self) -> Path:
        return self.data_dir / "llm-cache.sqlite"

    @property
    def export_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.blob_dir, self.export_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings(env_file: str | os.PathLike[str] | None = ".env") -> Settings:
    if env_file is not None:
        _load_dotenv(Path(env_file))

    mode = os.environ.get("FDIP_PROVIDER_MODE", "mock").strip().lower()
    if mode not in PROVIDER_MODES:
        raise ValueError(
            "FDIP_PROVIDER_MODE must be one of %s, not %r"
            % (", ".join(PROVIDER_MODES), mode)
        )

    data_dir = Path(os.environ.get("FDIP_DATA_DIR", "./data")).resolve()
    pepper = os.environ.get("FDIP_KEY_PEPPER", "")
    session_secret = os.environ.get("FDIP_SESSION_SECRET", "")
    # The pepper is required in **every** mode. It used to be generated outside
    # live mode as a convenience, and the convenience was that a local server
    # started happily with a brand-new pepper and left every key already in the
    # database failing to authenticate, with nothing in the logs to say why.
    # Silently invalidating credentials is not a convenience. `.env.example`
    # ships a placeholder; copy it.
    if len(pepper) < 16:
        raise ValueError(
            "FDIP_KEY_PEPPER must be set to at least 16 characters. "
            "A generated pepper would invalidate every API key already issued. "
            "Copy .env.example to .env and set one."
        )

    environment = os.environ.get("FDIP_ENV", "development").strip().lower()
    if environment == "production":
        # Refuse at startup rather than degrade at runtime. Each of these has a
        # default that is right locally and wrong in front of real users.
        if mode == "mock":
            raise ValueError(
                "FDIP_PROVIDER_MODE=mock is forbidden when FDIP_ENV=production: "
                "mock mode answers from canned fixtures, which would serve "
                "invented data that looks exactly like a real extraction"
            )
        if len(session_secret) < 16:
            raise ValueError(
                "FDIP_SESSION_SECRET must be set to at least 16 characters in "
                "production; a generated one logs every user out on restart"
            )
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise ValueError(
                "DEEPSEEK_API_KEY is required when FDIP_ENV=production"
            )
        if not os.environ.get("FDIP_AI_MONTHLY_CEILING_USD"):
            raise ValueError(
                "FDIP_AI_MONTHLY_CEILING_USD is required when "
                "FDIP_ENV=production: without it the bill is unbounded"
            )
    if mode == "live":
        # The session secret matters less: a generated one logs users out on
        # restart, which is recoverable. In live mode it is still required.
        if len(session_secret) < 16:
            raise ValueError(
                "FDIP_SESSION_SECRET must be set to at least 16 characters in live mode"
            )
        if not os.environ.get("DEEPSEEK_API_KEY"):
            raise ValueError("DEEPSEEK_API_KEY is required in live mode")
    session_secret = session_secret or secrets.token_hex(32)

    # Per route, because the two routes were measured differently and option (c)
    # was never actually measured at all -- see PHASE1_DECISION.md. Digital gets
    # reasoning on, which is the only setting with a 420-document result behind it.
    # Scans get option (c), where the extra reasoning is worth its cost because OCR
    # text is what the first attempt has to work from.
    thinking = os.environ.get("FDIP_EXTRACT_THINKING", "").strip().lower()
    digital = os.environ.get("FDIP_EXTRACT_THINKING_DIGITAL", "on").strip().lower()
    scan = os.environ.get("FDIP_EXTRACT_THINKING_SCAN", "repair").strip().lower()
    for name, value in (("FDIP_EXTRACT_THINKING", thinking),
                        ("FDIP_EXTRACT_THINKING_DIGITAL", digital),
                        ("FDIP_EXTRACT_THINKING_SCAN", scan)):
        if value and value not in ("on", "off", "repair"):
            raise ValueError("%s must be on, off or repair, not %r" % (name, value))

    origins = tuple(
        o.strip() for o in
        os.environ.get("FDIP_CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    )
    return Settings(
        data_dir=data_dir,
        db_url=os.environ.get("FDIP_DB_URL", "sqlite:///./data/fdip.db"),
        provider_mode=mode,
        model=os.environ.get("TOOLKIT_MODEL", "deepseek-flash"),
        extract_thinking=thinking,
        extract_thinking_digital=thinking or digital,
        extract_thinking_scan=thinking or scan,
        # Default false. Route B produced 13 silent errors in 30 mild scans, so a
        # scanned document is not auto-completed until `--final` proves otherwise.
        scan_auto_accept=_bool("FDIP_SCAN_AUTO_ACCEPT", False),
        key_pepper=pepper,
        session_secret=session_secret,
        monthly_ceiling_usd=float(
            os.environ.get("FDIP_AI_MONTHLY_CEILING_USD", "20") or 20
        ),
        cors_origins=origins,
        dev_seed=_bool("FDIP_DEV_SEED", mode != "live"),
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        environment=environment,
        allow_registration=_bool("FDIP_ALLOW_REGISTRATION", True),
        login_attempts_per_minute=int(
            os.environ.get("FDIP_LOGIN_ATTEMPTS_PER_MINUTE", "10")),
        uploads_per_minute=int(os.environ.get("FDIP_UPLOADS_PER_MINUTE", "30")),
    )


_cached: Settings | None = None


def settings() -> Settings:
    global _cached
    if _cached is None:
        _cached = load_settings()
    return _cached


def override(new: Settings | None) -> None:
    """Used by tests and by the CLI to point at a temporary data directory."""
    global _cached
    _cached = new


__all__ = ["PROVIDER_MODES", "Settings", "load_settings", "override", "settings"]

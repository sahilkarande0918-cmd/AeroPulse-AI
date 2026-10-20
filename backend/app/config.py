import logging
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_env: str = "development"            # development | production
    database_url: str = f"sqlite:///{(REPO_ROOT / 'backend' / 'aeropulse_dev.db').as_posix()}"
    jwt_secret_key: str = ""
    jwt_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"
    demo_password: str = ""                  # seeds demo users; random if unset
    llm_enabled: bool = False
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    max_upload_bytes: int = 5_000_000
    demo_reset_enabled: bool = False         # allow admins to wipe and re-seed the synthetic demo (demo hosting only)
    # Organisation SSO: AUTH_MODE=oidc validates IdP-signed bearer tokens instead of local passwords.
    auth_mode: str = "local"                 # local | oidc
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_username_claim: str = "preferred_username"
    oidc_groups_claim: str = "groups"
    oidc_role_map: str = ""                  # "idp-group=role,other-group=role"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("aeropulse")

if not settings.jwt_secret_key:
    if settings.is_production:
        raise RuntimeError("JWT_SECRET_KEY must be set when APP_ENV=production")
    # ponytail: per-process dev secret, tokens die on restart; set JWT_SECRET_KEY for stable sessions.
    settings.jwt_secret_key = secrets.token_urlsafe(48)
    log.warning("JWT_SECRET_KEY not set; using an ephemeral development secret")

# Prototype decision thresholds. NOT certified maintenance standards; editable by admins at runtime.
DEFAULT_TRUST_THRESHOLDS = {
    "stale_degraded_hours": 48,
    "stale_unavailable_hours": 240,
    "min_history_cycles": 5,
    "min_history_valid_cycles": 20,
    "max_missing_sensors_degraded": 2,      # more missing model sensors -> UNAVAILABLE
    "spike_sigma": 8.0,                     # step change vs typical cycle-to-cycle variation
    "plausibility_sigma": 8.0,              # beyond training range by this many std -> invalid
    "ood_fraction_degraded": 0.25,          # share of features outside training p0.5-p99.5
    "ood_fraction_unavailable": 0.6,
    "rul_critical_lower_bound": 15,         # cycles; lower interval bound triggers planning
    "rul_warning_lower_bound": 40,
    "cycles_per_day": 2,                    # fleet utilisation assumption for due dates
}

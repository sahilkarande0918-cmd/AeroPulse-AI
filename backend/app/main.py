from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, fleet, ingestion, maintenance, parts, reports, system, trusttwin
from app.config import log, settings
from app.services import simulator
from app.services import trusttwin as trusttwin_service
from ml.inference import load_model


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load the model and precompute hold-out predictions once, so no user request pays for it.
    try:
        load_model()
        simulator.trajectory_table()
        trusttwin_service.holdout_raw()
    except FileNotFoundError as e:
        log.error("warm-up skipped: %s", e)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AeroPulse AI API",
    version="1.0.0",
    description="Advisory predictive-maintenance decision support (SIH26249 prototype). "
                "Outputs are advisory only and never constitute airworthiness or dispatch decisions.",
)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH"],
                   allow_headers=["Authorization", "Content-Type"])


def _error(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details}})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    code = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict",
            413: "payload_too_large", 422: "unprocessable", 429: "rate_limited", 503: "unavailable"}.get(exc.status_code, "error")
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    details = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return _error(422, "validation_error", "Request validation failed", details)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled error")
    return _error(500, "internal_error", "Internal server error")


@app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)   # UptimeRobot probes with HEAD
def liveness():
    """Uptime-monitor ping: no database or model access, so pings never wake or bill the database."""
    return {"status": "ok"}


for r in (system.router, auth.router, fleet.router, maintenance.router, parts.router, trusttwin.router,
          ingestion.router, reports.router):
    app.include_router(r, prefix="/api")

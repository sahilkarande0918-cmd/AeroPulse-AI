"""Cross-platform dev entry point.

    python manage.py migrate   # alembic upgrade head on DATABASE_URL
    python manage.py seed      # synthetic demo fleet (idempotent)
    python manage.py serve     # API on http://127.0.0.1:8000
    python manage.py start     # containers: migrate + seed + serve on 0.0.0.0:$PORT in ONE process (imports once)
    python manage.py train     # retrain the model from the NASA archive
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def main(cmd: str) -> None:
    if cmd == "start":
        for step in ("migrate", "seed"):
            main(step)
        import uvicorn
        uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")),  # noqa: S104 (container)
                    proxy_headers=True, workers=1)
    elif cmd == "migrate":
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config(str(ROOT / "backend" / "alembic.ini")), "head")
    elif cmd == "seed":
        from app.database import SessionLocal
        from app.seed import seed
        with SessionLocal() as s:
            seed(s)
    elif cmd == "serve":
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
    elif cmd == "train":
        from ml.train import main as train
        train()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")

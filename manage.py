"""Cross-platform dev entry point.

    python manage.py migrate   # alembic upgrade head on DATABASE_URL
    python manage.py seed      # synthetic demo fleet (idempotent)
    python manage.py serve     # API on http://127.0.0.1:8000
    python manage.py train     # retrain the model from the NASA archive
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def main(cmd: str) -> None:
    if cmd == "migrate":
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

import os
from pathlib import Path
import shutil
import sys

# Ensure project root is available on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# On Vercel serverless environment, setup writable storage in /tmp
if os.environ.get("VERCEL"):
    tmp_data = Path("/tmp/data")
    try:
        tmp_data.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    tmp_db = tmp_data / "testkart.db"
    bundled_db = BASE_DIR / "data" / "testkart.db"

    if bundled_db.exists() and not tmp_db.exists():
        try:
            shutil.copy2(bundled_db, tmp_db)
        except Exception as e:
            print(f"Warning: Could not copy bundled DB to /tmp: {e}")

    # Override runtime environment for Vercel
    os.environ["TESTKART_DATABASE_PATH"] = str(tmp_db)
    os.environ["TESTKART_ENABLE_BACKGROUND_SCHEDULER"] = "false"

from testkart_intelligence.api.app import app

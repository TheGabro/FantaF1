"""Impostazioni SOLO per l'anteprima di sviluppo del frontend.

Lavora su una copia isolata del database (frontend/dev_db.sqlite3) per non
toccare i dati reali di db.sqlite3. La copia viene creata al primo avvio;
cancellarla per ripartire da uno stato pulito.

Avvio: .venv\\Scripts\\python.exe manage.py runserver 8137 --settings=dev_settings
"""
import shutil
from pathlib import Path

from FantaF1.settings import *  # noqa: F401,F403

_ROOT = Path(__file__).resolve().parent
_DEV_DB = _ROOT / "frontend" / "dev_db.sqlite3"

if not _DEV_DB.exists():
    shutil.copyfile(_ROOT / "db.sqlite3", _DEV_DB)

# Si ridefinisce l'intera entry, non solo NAME: se .env contiene DATABASE_URL le
# impostazioni base puntano a Postgres, e sostituire il solo NAME lascerebbe
# l'anteprima collegata al database remoto.
DATABASES = {  # noqa: F405
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _DEV_DB,
    }
}

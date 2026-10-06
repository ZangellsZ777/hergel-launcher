"""Non-secret preferences, stored separately from the encrypted session."""
import json
import os
import sys
import tempfile
from pathlib import Path

DATA_DIR = (Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'HergelLauncher'
            if sys.platform == 'win32' else Path.home() / '.local/share/HergelLauncher')
SETTINGS_PATH = DATA_DIR / 'settings.json'


def load_settings():
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(**changes):
    data = load_settings()
    data.update(changes)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=DATA_DIR, prefix='.settings-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp, SETTINGS_PATH)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def ram_mb(value):
    try:
        number = int(value)
    except (ValueError, TypeError):
        raise ValueError('Elige la RAM entre 2 y 16 GB.')
    if number < 2 or number > 16:
        raise ValueError('Elige la RAM entre 2 y 16 GB.')
    return number * 1024

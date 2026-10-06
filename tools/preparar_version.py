from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hergel.version import VERSION
from hergel.updater import update_config, version_tuple
version_tuple(VERSION)
if not update_config():
    raise SystemExit('Configura primero el repositorio: py tools\\configurar_actualizaciones.py USUARIO/REPOSITORIO')
root = Path(__file__).resolve().parent.parent
(root / 'build-windows/version.iss').write_text('#define HergelVersion "' + VERSION + '"\n', encoding='utf-8')
print('Version del instalador:', VERSION)

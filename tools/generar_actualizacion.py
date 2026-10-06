"""Generate the release announcement only from a finished installer."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hergel.version import VERSION
from hergel.updater import update_config, validate_release, version_tuple
parser = argparse.ArgumentParser(description='Crear el anuncio de una version del launcher')
parser.add_argument('installer', type=Path)
parser.add_argument('--minima', default='0.0.0', help='Version minima que puede seguir jugando; 0.0.0 = opcional')
parser.add_argument('--notas', default='Mejoras de Hergel Launcher.')
parser.add_argument('--output', type=Path, default=Path('dist/launcher-update.json'))
args = parser.parse_args()
config = update_config()
if not config:
    parser.error('Configura antes el repositorio con configurar_actualizaciones.py')
version_tuple(args.minima)
if not args.installer.is_file() or args.installer.suffix.lower() != '.exe':
    parser.error('Indica un instalador .exe existente')
if args.installer.name != 'Hergel-Launcher-Instalador.exe':
    parser.error('El instalador debe llamarse Hergel-Launcher-Instalador.exe')
with args.installer.open('rb') as f:
    sha = hashlib.file_digest(f, 'sha256').hexdigest()
release = {'schema': 1, 'version': VERSION, 'minimum_supported': args.minima,
    'installer_url': f'https://github.com/{config["repository"]}/releases/download/v{VERSION}/{args.installer.name}',
    'sha256': sha, 'size': args.installer.stat().st_size, 'notes': args.notas}
validate_release(release, config)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding='utf-8')
print('Anuncio generado:', args.output)
print('Publica el instalador y este anuncio en la release v' + VERSION)

"""Set the internal repository once, before building the player installer."""
import argparse
import json
import re
from pathlib import Path
parser = argparse.ArgumentParser(description='Configurar el alojamiento de actualizaciones del launcher')
parser.add_argument('repository', help='USUARIO/REPOSITORIO de GitHub, publico')
args = parser.parse_args()
if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
    parser.error('Usa el formato USUARIO/REPOSITORIO')
path = Path(__file__).resolve().parent.parent / 'launcher_updates.json'
path.write_text(json.dumps({'repository': args.repository,
    'feed_url': f'https://github.com/{args.repository}/releases/latest/download/launcher-update.json'}, indent=2), encoding='utf-8')
print('Alojamiento configurado. Ya puedes crear el instalador.')

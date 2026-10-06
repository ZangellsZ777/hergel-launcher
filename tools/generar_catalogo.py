"""Generate a remote-update catalog from a clean client pack ZIP."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from hergel.pack import validate_remote_package


def main():
    parser = argparse.ArgumentParser(description='Generar catálogo de actualizaciones de El Hormiguero')
    parser.add_argument('zip', type=Path)
    parser.add_argument('url', help='URL HTTPS de descarga directa del ZIP')
    parser.add_argument('--output', type=Path, default=Path('catalog.json'))
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as z:
        package = {'url': args.url, 'size': args.zip.stat().st_size,
                   'sha256': hashlib.sha256(args.zip.read_bytes()).hexdigest(),
                   'files': [{'path': n, 'size': z.getinfo(n).file_size,
                              'sha256': hashlib.sha256(z.read(n)).hexdigest()}
                             for n in z.namelist() if not n.endswith('/')]}
    validate_remote_package(package)
    catalog = {'schema': 1, 'packs': [{'id': 'el-hormiguero', 'name': 'El Hormiguero',
        'minecraft': '1.20.1', 'loader': 'forge', 'forge': '47.4.10',
        'server': 'ElHormiguero.exaroton.me:39146', 'files': [], 'package': package}]}
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Catálogo generado:', args.output)


if __name__ == '__main__':
    main()

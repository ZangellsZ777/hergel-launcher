"""Fetch the release asset for builds; refuse partial or altered downloads."""
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    meta = json.loads((root / 'pack-source.json').read_text())
    target = root / 'packs/hormiguero.zip'
    expected = json.loads((root / 'packs/hormiguero.json').read_text())
    if any(meta[key] != expected[key] for key in ('url', 'size', 'sha256')):
        raise ValueError('El paquete fuente y el manifiesto no coinciden.')
    if target.exists() and target.stat().st_size == meta['size']:
        with target.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() == meta['sha256']:
                return
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent)
    try:
        request = urllib.request.Request(meta['url'], headers={'User-Agent': 'Hergel-Build'})
        with os.fdopen(fd, 'wb') as output, urllib.request.urlopen(request, timeout=120) as response:
            if not response.geturl().startswith('https://'):
                raise ValueError('Descarga sin HTTPS.')
            total = 0
            digest = hashlib.sha256()
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > meta['size']:
                    raise ValueError('Tamaño de paquete incorrecto.')
                digest.update(chunk)
                output.write(chunk)
        if total != meta['size'] or digest.hexdigest() != meta['sha256']:
            raise ValueError('Paquete incompleto o alterado.')
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    main()

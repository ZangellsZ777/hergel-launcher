import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

MAX_MANIFEST = 2 * 1024 * 1024
MAX_FILE = 1024 * 1024 * 1024
ALLOWED_ROOTS = {'mods', 'config', 'defaultconfigs', 'resourcepacks', 'shaderpacks', 'kubejs'}
HEX_SHA = re.compile(r'^[0-9a-f]{64}$')


def validate_manifest(data):
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise ValueError('Formato de catálogo incompatible')
    packs = data.get('packs')
    if not isinstance(packs, list) or len(packs) > 100:
        raise ValueError('Lista de modalidades inválida')
    seen = set()
    for pack in packs:
        if not isinstance(pack, dict) or not isinstance(pack.get('id'), str) or not re.fullmatch(r'[a-z0-9_-]{1,40}', pack['id']):
            raise ValueError('ID de modalidad inválido')
        if pack['id'] in seen:
            raise ValueError('Modalidad duplicada')
        seen.add(pack['id'])
        if not isinstance(pack.get('name'), str) or len(pack['name']) > 80 or not pack['name']:
            raise ValueError('Nombre inválido')
        if pack.get('package') is not None:
            from .pack import validate_remote_package
            validate_remote_package(pack['package'])
        files = pack.get('files')
        if not isinstance(files, list) or len(files) > 1000:
            raise ValueError('Lista de archivos inválida')
        paths = set()
        for item in files:
            if not isinstance(item, dict):
                raise ValueError('Archivo inválido')
            relative = item.get('path')
            if not isinstance(relative, str) or '\\' in relative or not relative.isascii():
                raise ValueError('Ruta inválida')
            parts = relative.split('/')
            if len(parts) < 2 or parts[0] not in ALLOWED_ROOTS or any(p in ('', '.', '..') or ':' in p for p in parts):
                raise ValueError('Ruta fuera de la instancia')
            if relative.lower() in paths:
                raise ValueError('Archivo duplicado')
            paths.add(relative.lower())
            url = item.get('url')
            parsed = urlparse(url) if isinstance(url, str) else None
            if not parsed or parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError('Se requiere una URL HTTPS')
            if not isinstance(item.get('sha256'), str) or not HEX_SHA.fullmatch(item['sha256']):
                raise ValueError('SHA-256 inválido')
            if type(item.get('size')) is not int or not 0 <= item['size'] <= MAX_FILE:
                raise ValueError('Tamaño inválido')
    return packs


def load_catalog(source):
    if source.startswith('https://'):
        with urllib.request.urlopen(source, timeout=20) as response:
            raw = response.read(MAX_MANIFEST + 1)
    elif source.startswith('http://'):
        raise ValueError('El catálogo remoto requiere HTTPS')
    else:
        raw = Path(source).read_bytes()
    if len(raw) > MAX_MANIFEST:
        raise ValueError('Catálogo demasiado grande')
    data = json.loads(raw)
    validate_manifest(data)
    return data


def matches(path, entry):
    if not path.is_file() or path.is_symlink() or path.stat().st_size != entry['size']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest() == entry['sha256']


def install(pack, root, report=lambda message: None):
    validate_manifest({'schema': 1, 'packs': [pack]})
    destination = Path(root).expanduser() / pack['id']
    destination.mkdir(parents=True, exist_ok=True)
    for entry in pack['files']:
        target = destination.joinpath(*entry['path'].split('/'))
        if any(p.is_symlink() for p in (target, *target.parents) if p != destination.parent):
            raise ValueError('Enlace simbólico en la ruta de instalación')
        if matches(target, entry):
            report('Verificado: ' + entry['path'])
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        report('Descargando: ' + entry['path'])
        fd, temp_name = tempfile.mkstemp(prefix='.hergel-', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as output:
                request = urllib.request.Request(entry['url'], headers={'User-Agent': 'HergelLauncher/0.1'})
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.geturl().startswith('http://'):
                        raise ValueError('Redirección no segura')
                    total = 0
                    digest = hashlib.sha256()
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > entry['size']:
                            raise ValueError('Descarga mayor que el tamaño declarado')
                        digest.update(chunk)
                        output.write(chunk)
            if total != entry['size'] or digest.hexdigest() != entry['sha256']:
                raise ValueError('La descarga no coincide con SHA-256: ' + entry['path'])
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    return destination

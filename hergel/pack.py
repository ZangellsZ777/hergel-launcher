"""Install the bundled event pack and keep player settings on updates."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
import urllib.request
from urllib.parse import urlparse
from .settings import DATA_DIR
from pathlib import Path, PurePosixPath

PACKS = Path(__file__).resolve().parent.parent / 'packs'
STATE = '.hergel-install.json'
ROOTS = {'mods', 'config', 'emotes', 'resourcepacks', 'shaderpacks', 'defaultconfigs', 'kubejs'}


def bundle_data(pack):
    if pack.get('package') is not None:
        meta = pack['package']
        validate_remote_package(meta)
        return meta
    name = pack.get('bundle')
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_-]+', name):
        raise ValueError('Falta el paquete de la modalidad.')
    meta = json.loads((PACKS / (name + '.json')).read_text(encoding='utf-8'))
    if Path(meta['archive']).name != meta['archive']:
        raise ValueError('Ruta del paquete inválida.')
    seen = set()
    for entry in meta['files']:
        path = entry['path']
        parts = PurePosixPath(path).parts
        if (not parts or '\\' in path or ':' in path or path.startswith('/')
                or any(p in ('', '.', '..') for p in path.split('/'))
                or (path != 'options.txt' and (len(parts) < 2 or parts[0] not in ROOTS))
                or path.casefold() in seen):
            raise ValueError('Ruta inválida en el paquete: ' + path)
        seen.add(path.casefold())
    return meta


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def safe_target(folder, relative):
    target = folder.joinpath(*relative.split('/'))
    for p in (target, *target.parents):
        if p.is_symlink():
            raise ValueError('Enlace simbólico en la instancia.')
        if p == folder:
            break
    return target


def read_state(folder):
    try:
        return json.loads((folder / STATE).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def install_bundle(pack, folder, report=lambda message: None,
                   progress=lambda stage, current, total: None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    meta = bundle_data(pack)
    archive = fetch_package(meta, report, progress) if pack.get('package') else PACKS / meta['archive']
    report('Verificando el paquete de El Hormiguero...')
    if digest(archive) != meta['sha256']:
        raise ValueError('El paquete está dañado. Descarga de nuevo el launcher.')
    old = read_state(folder)
    old_files = {e['path']: e for e in old.get('files', [])}
    entries = meta['files']
    total = sum(e['size'] for e in entries)
    done = 0
    # Validate every byte before writing any event file into the instance.
    with tempfile.TemporaryDirectory(prefix='.hergel-pack-', dir=folder.parent) as temp:
        staging = Path(temp)
        with zipfile.ZipFile(archive) as z:
            if set(z.namelist()) != {e['path'] for e in entries}:
                raise ValueError('El contenido del paquete no coincide con su manifiesto.')
            for entry in entries:
                n = entry['path']
                data = z.read(n)
                if len(data) != entry['size'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                    raise ValueError('Archivo del paquete dañado: ' + n)
                staged = staging / n
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(data)
        for entry in entries:
            n = entry['path']
            target = safe_target(folder, n)
            previous = old_files.get(n)
            personal = n == 'options.txt' or (n.startswith('config/') and not n.startswith('config/fancymenu/'))
            preserve = (personal and target.is_file() and previous is not None
                        and digest(target) != previous['sha256'])
            if not preserve:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / n, target)
            done += entry['size']
            report(('Conservando tus ajustes: ' if preserve else 'Instalando: ') + n)
            progress('Paquete de El Hormiguero', done, total)
        current = {e['path'] for e in entries}
        # Only remove obsolete managed binaries; never delete player-added files.
        for n in old_files:
            if n not in current and n.startswith('mods/'):
                target = safe_target(folder, n)
                if target.is_file():
                    target.unlink()


def mark_ready(pack, folder, version):
    meta = bundle_data(pack)
    state = {'ready': True, 'minecraft': pack['minecraft'], 'forge': pack['forge'],
             'version': version, 'bundle_sha256': meta['sha256'], 'files': meta['files']}
    folder = Path(folder)
    temp = folder / (STATE + '.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, folder / STATE)


def installed_game(pack, root):
    folder = Path(root).expanduser() / pack['id']
    try:
        state = read_state(folder)
        meta = bundle_data(pack)
        version = state['version']
        if (not state.get('ready') or state['bundle_sha256'] != meta['sha256']
                or state['minecraft'] != pack['minecraft'] or state['forge'] != pack['forge']
                or not (folder / 'versions' / version / (version + '.json')).is_file()):
            return None
        import minecraft_launcher_lib
        java = minecraft_launcher_lib.runtime.get_executable_path('java-runtime-gamma', str(folder))
        if not java or not Path(java).is_file():
            return None
        for entry in meta['files']:
            path = safe_target(folder, entry['path'])
            if not path.is_file():
                return None
            if entry['path'].startswith('mods/') and digest(path) != entry['sha256']:
                return None
        return folder, version
    except (OSError, ValueError, KeyError, ImportError):
        return None


def validate_remote_package(meta):
    if not isinstance(meta, dict):
        raise ValueError('Paquete remoto inválido.')
    url = urlparse(meta.get('url', ''))
    if url.scheme != 'https' or not url.netloc or url.username or url.password:
        raise ValueError('El paquete remoto requiere HTTPS.')
    if type(meta.get('size')) is not int or not 0 < meta['size'] <= 1024 ** 3:
        raise ValueError('Tamaño del paquete remoto inválido.')
    if not re.fullmatch(r'[a-f0-9]{64}', str(meta.get('sha256', ''))):
        raise ValueError('SHA-256 del paquete inválido.')
    entries = meta.get('files')
    if not isinstance(entries, list) or not 1 <= len(entries) <= 10000:
        raise ValueError('Lista de archivos del paquete inválida.')
    paths = set()
    total = 0
    for entry in entries:
        n = entry.get('path', '')
        parts = n.split('/')
        if (not n or '\\' in n or ':' in n or n.startswith('/')
                or any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in parts)
                or (n != 'options.txt' and (len(parts) < 2 or parts[0] not in ROOTS))
                or n.casefold() in paths):
            raise ValueError('Ruta fuera de la instancia: ' + n)
        paths.add(n.casefold())
        if type(entry.get('size')) is not int or not 0 <= entry['size'] <= 1024 ** 3:
            raise ValueError('Tamaño de archivo inválido.')
        if not re.fullmatch(r'[a-f0-9]{64}', str(entry.get('sha256', ''))):
            raise ValueError('SHA-256 de archivo inválido.')
        total += entry['size']
    if total > 2 * 1024 ** 3:
        raise ValueError('El paquete descomprimido es demasiado grande.')


def fetch_package(meta, report, progress):
    bundled = PACKS / 'hormiguero.zip'
    if bundled.is_file() and bundled.stat().st_size == meta['size'] and digest(bundled) == meta['sha256']:
        report('Usando el paquete incluido y verificado.')
        return bundled
    cache = DATA_DIR / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (meta['sha256'] + '.zip')
    if path.is_file() and path.stat().st_size == meta['size'] and digest(path) == meta['sha256']:
        return path
    report('Descargando la actualización de El Hormiguero...')
    fd, temp = tempfile.mkstemp(prefix='.download-', dir=cache)
    try:
        request = urllib.request.Request(meta['url'], headers={'User-Agent': 'HergelLauncher/0.18'})
        with os.fdopen(fd, 'wb') as output, urllib.request.urlopen(request, timeout=60) as response:
            if urlparse(response.geturl()).scheme != 'https':
                raise ValueError('Redirección de descarga no segura.')
            count = 0
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > meta['size']:
                    raise ValueError('La descarga excede el tamaño declarado.')
                output.write(chunk)
                progress('Descarga del paquete', count, meta['size'])
        if count != meta['size'] or digest(temp) != meta['sha256']:
            raise ValueError('La actualización está incompleta o dañada. Vuelve a pulsar Descargar.')
        os.replace(temp, path)
        return path
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

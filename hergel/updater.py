"""Opt-in installer updates from the configured public GitHub Releases feed."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from .settings import DATA_DIR
from .version import VERSION

APP_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_ROOT / 'launcher_updates.json'
MAX_INSTALLER = 1024 ** 3


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,4}\.\d{1,4}\.\d{1,4}', value):
        raise ValueError('Versión de launcher inválida.')
    return tuple(map(int, value.split('.')))


def update_config(path=CONFIG_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    repository = data.get('repository', '')
    url = data.get('feed_url', '')
    if not repository and not url:
        return None
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Repositorio de actualizaciones inválido.')
    expected = f'https://github.com/{repository}/releases/latest/download/launcher-update.json'
    if url != expected:
        raise ValueError('La dirección de actualizaciones no corresponde al repositorio configurado.')
    return data


def validate_release(data, config):
    if not isinstance(data, dict) or data.get('schema') != 1:
        raise ValueError('Anuncio de actualización inválido.')
    latest = version_tuple(data.get('version'))
    minimum = version_tuple(data.get('minimum_supported', '0.0.0'))
    if minimum > latest:
        raise ValueError('La versión mínima supera la versión publicada.')
    url = data.get('installer_url', '')
    expected = f'https://github.com/{config["repository"]}/releases/download/'
    parsed = urlparse(url)
    if (not url.startswith(expected) or parsed.query or parsed.fragment
            or parsed.username or parsed.password or not parsed.path.endswith('.exe')
            or any(p in ('.', '..') for p in parsed.path.split('/'))):
        raise ValueError('El instalador debe pertenecer al repositorio de Hergel Launcher.')
    if not re.fullmatch(r'[a-f0-9]{64}', str(data.get('sha256', ''))):
        raise ValueError('Falta la huella SHA-256 del instalador.')
    if type(data.get('size')) is not int or not 0 < data['size'] <= MAX_INSTALLER:
        raise ValueError('Tamaño de instalador inválido.')
    if not isinstance(data.get('notes', ''), str) or len(data.get('notes', '')) > 4000:
        raise ValueError('Notas de actualización inválidas.')
    return data


def check_update(config=None):
    config = config if config is not None else update_config()
    if not config:
        return None
    request = urllib.request.Request(config['feed_url'], headers={
        'User-Agent': 'HergelLauncher/' + VERSION, 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=15) as response:
        if urlparse(response.geturl()).scheme != 'https':
            raise ValueError('Redirección de actualizaciones no segura.')
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError('Anuncio de actualización demasiado grande.')
    release = validate_release(json.loads(raw), config)
    if version_tuple(release['version']) <= version_tuple(VERSION):
        return None
    return {**release, 'required': version_tuple(VERSION) < version_tuple(release.get('minimum_supported', '0.0.0'))}


def sha256(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def download_update(release, progress=lambda current, total: None):
    validate_release(release, update_config())
    folder = DATA_DIR / 'updates'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ('Hergel-Setup-' + release['version'] + '.exe')
    if target.is_file() and target.stat().st_size == release['size'] and sha256(target) == release['sha256']:
        progress(release['size'], release['size'])
        return target
    fd, temp = tempfile.mkstemp(prefix='.installer-', dir=folder)
    try:
        request = urllib.request.Request(release['installer_url'], headers={'User-Agent': 'HergelLauncher/' + VERSION})
        with os.fdopen(fd, 'wb') as output, urllib.request.urlopen(request, timeout=60) as response:
            if urlparse(response.geturl()).scheme != 'https':
                raise ValueError('Redirección del instalador no segura.')
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > release['size']:
                    raise ValueError('El instalador excede el tamaño anunciado.')
                output.write(chunk)
                progress(size, release['size'])
        if size != release['size'] or sha256(temp) != release['sha256']:
            raise ValueError('La descarga está incompleta o dañada. Inténtalo de nuevo.')
        os.replace(temp, target)
        return target
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def launch_installer(installer, release):
    if sys.platform != 'win32':
        raise RuntimeError('La actualización automática del instalador requiere Windows.')
    if installer.stat().st_size != release['size'] or sha256(installer) != release['sha256']:
        raise ValueError('No se puede ejecutar un instalador sin verificar.')
    folder = DATA_DIR / 'updates'
    helper = folder / 'hergel-update.ps1'
    shutil.copy2(APP_ROOT / 'tools' / 'hergel-update.ps1', helper)
    target = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
              else Path(os.environ['LOCALAPPDATA']) / 'Programs' / 'HergelLauncher')
    request = folder / 'install-request.json'
    request.write_text(json.dumps({'pid': os.getpid(), 'installer': str(installer.resolve()),
        'install_dir': str(target), 'sha256': release['sha256']}), encoding='utf-8')
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    return subprocess.Popen([str(powershell), '-NoProfile', '-NonInteractive',
        '-ExecutionPolicy', 'Bypass', '-File', str(helper), '-RequestPath', str(request)],
        creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)

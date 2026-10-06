"""Install the game into one pack directory and launch with a verified Java profile."""
import subprocess
import os
import shutil
import sys
import json
from pathlib import Path

from .core import install, validate_manifest
from .settings import ram_mb
from .version import VERSION
from .pack import install_bundle, mark_ready, read_state, STATE


def prepare_game(pack, root, report=lambda message: None,
                 progress=lambda stage, current, total: None):
    validate_manifest({'schema': 1, 'packs': [pack]})
    if pack.get('loader') != 'forge' or not pack.get('minecraft') or not pack.get('forge'):
        raise ValueError('El catálogo debe declarar la versión de Minecraft y Forge.')
    try:
        import minecraft_launcher_lib
    except ImportError as exc:
        raise RuntimeError('Instala las dependencias: py -m pip install -r requirements.txt') from exc
    folder = Path(root).expanduser() / pack['id']
    # Preserve an existing instance when switching from the old visible default.
    previous = Path.home() / 'HergelLauncher' / 'instances' / pack['id']
    if (sys.platform == 'win32' and os.environ.get('LOCALAPPDATA')
            and Path(root).expanduser() == Path(os.environ['LOCALAPPDATA']) / 'HergelLauncher' / 'instances'
            and previous.is_dir() and not folder.exists()):
        folder.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(previous), str(folder))
    folder.mkdir(parents=True, exist_ok=True)
    state = read_state(folder)
    state['ready'] = False
    (folder / STATE).write_text(json.dumps(state), encoding='utf-8')
    def callbacks(stage):
        state = {'maximum': 0}

        def set_max(value):
            state['maximum'] = max(0, int(value))
            progress(stage, 0, state['maximum'])

        def set_progress(value):
            progress(stage, int(value), state['maximum'])

        return {'setStatus': lambda message: report(f'{stage}: {message}'),
                'setProgress': set_progress, 'setMax': set_max}

    report('Instalando y verificando Minecraft ' + pack['minecraft'])
    minecraft_launcher_lib.install.install_minecraft_version(
        pack['minecraft'], str(folder), callback=callbacks('Minecraft'))
    java = minecraft_launcher_lib.runtime.get_executable_path('java-runtime-gamma', str(folder))
    if not java or not Path(java).is_file():
        raise RuntimeError('No se pudo instalar Java 17. Vuelve a pulsar Descargar.')
    loader = minecraft_launcher_lib.mod_loader.get_mod_loader('forge')
    version = loader.get_installed_version(pack['minecraft'], pack['forge'])
    if not (folder / 'versions' / version / (version + '.json')).is_file():
        report('Instalando Forge ' + pack['forge'])
        version = loader.install(pack['minecraft'], str(folder), loader_version=pack['forge'],
                                 callback=callbacks('Forge'), java=java)
    else:
        minecraft_launcher_lib.install.install_minecraft_version(
            version, str(folder), callback=callbacks('Forge'))
    progress('Archivos de la modalidad', 0, 0)
    report('Verificando archivos de la modalidad...')
    install(pack, root, report)
    install_bundle(pack, folder, report, progress)
    mark_ready(pack, folder, version)
    return folder, version


def launch_game(folder, version, minecraft_account, server=None, memory_gb=4):
    try:
        import minecraft_launcher_lib
    except ImportError as exc:
        raise RuntimeError('Instala las dependencias: py -m pip install -r requirements.txt') from exc
    if not all(minecraft_account.get(key) for key in ('minecraft_name', 'minecraft_id', 'minecraft_token')):
        raise ValueError('Inicia sesión con una cuenta propietaria de Minecraft Java.')
    folder = Path(folder)
    options = {
        'username': minecraft_account['minecraft_name'],
        'uuid': minecraft_account['minecraft_id'],
        'token': minecraft_account['minecraft_token'],
        'gameDirectory': str(folder),
        'launcherName': 'Hergel Launcher',
        'launcherVersion': VERSION,
        'jvmArguments': ['-Xms512M', '-Xmx' + str(ram_mb(memory_gb)) + 'M'],
    }
    java = minecraft_launcher_lib.runtime.get_executable_path('java-runtime-gamma', str(folder))
    if not java or not Path(java).is_file():
        raise RuntimeError('Falta Java 17. Pulsa Descargar para reparar la instalación.')
    options['executablePath'] = java
    if server and server != 'PENDIENTE_DE_CONFIGURAR':
        host, _, port = server.partition(':')
        options['server'] = host
        if port:
            options['port'] = port
    command = minecraft_launcher_lib.command.get_minecraft_command(version, str(folder), options)
    return subprocess.Popen(command, cwd=folder)

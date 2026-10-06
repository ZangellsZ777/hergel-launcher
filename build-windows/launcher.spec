from pathlib import Path
from PyInstaller.utils.hooks import collect_all
base = Path(SPECPATH).parent
extra_data, extra_bins, extra_imports = [], [], []
for package in ['minecraft_launcher_lib', 'msal', 'msal_extensions', 'requests', 'PIL']:
    data, binaries, hidden = collect_all(package)
    extra_data += data
    extra_bins += binaries
    extra_imports += hidden
a = Analysis([str(base / 'run.py')], pathex=[str(base)],
    binaries=extra_bins, datas=extra_data + [(str(base / name), name) for name in ['assets', 'examples', 'tools']] +
    [(str(base / 'packs' / 'hormiguero.json'), 'packs')] +
    [(str(base / 'microsoft_app.json'), '.'), (str(base / 'launcher_updates.json'), '.')],
    hiddenimports=extra_imports, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HergelLauncher',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    icon=str(base / 'assets/hergel.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='HergelLauncher')

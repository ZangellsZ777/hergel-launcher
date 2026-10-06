"""Offline smoke check for the actual packaged Windows executable."""
import json
import traceback
from pathlib import Path
from unittest.mock import patch


def main(output):
    app = None
    result = {'ok': False}
    try:
        from .gui import App
        from .updater import update_config
        from .core import load_catalog
        from .pack import PACKS, bundle_data, validate_remote_package
        from .microsoft_auth import get_client_id
        root = PACKS.parent
        config = update_config()
        assert config, 'Falta el repositorio de actualizaciones'
        assert get_client_id(), 'Falta el ID de Microsoft'
        pack = load_catalog(str(root / 'examples/catalog.json'))['packs'][0]
        meta = bundle_data(pack)
        validate_remote_package(meta)
        assert meta['url'].startswith(f'https://github.com/{config["repository"]}/releases/download/'), 'El manifiesto apunta a otro repositorio'
        assert not (PACKS / 'hormiguero.zip').exists(), 'El instalador ligero incluye el modpack'
        with patch.object(App, 'load', lambda self: None), patch.object(App, 'restore_login', lambda self: None), patch.object(App, 'check_launcher_updates', lambda self: None), patch('hergel.gui.load_settings', return_value={}):
            app = App()
            app.withdraw()
            app.update_idletasks()
            app.show_settings()
            assert app.settings_dialog.winfo_exists(), 'No abre Ajustes'
            app.settings_dialog.destroy()
            app.launcher_update = {'version':'999.0.0', 'required':False, 'notes':'Verificación automática'}
            app.show_launcher_update()
            assert app.update_dialog.winfo_exists(), 'No abre el aviso de actualización'
            app.update_dialog.destroy()
        result = {'ok':True, 'checks':['configuración', 'manifiesto de descarga', 'modpack excluido', 'ventana principal', 'ajustes', 'aviso de actualización']}
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        if app is not None:
            app.destroy()
        Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1

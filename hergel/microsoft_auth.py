"""Microsoft login with encrypted Windows persistence and silent renewal."""
import json
import re
import sys
import threading
from pathlib import Path
from .settings import DATA_DIR, load_settings, save_settings

CONFIG_PATH = Path(__file__).resolve().parent.parent / 'microsoft_app.json'
AUTH_LOCK = threading.Lock()
MEMORY_CACHE = None


def get_client_id(path=CONFIG_PATH):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    value = data.get('client_id', '')
    if not value:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-fA-F-]{36}', value):
        raise ValueError('El client_id debe ser el identificador UUID de la aplicación registrada.')
    return value


def cache_path(client_id):
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', client_id):
        raise ValueError('ID de aplicación inválido.')
    return DATA_DIR / ('session-' + client_id.lower() + '.bin')


def token_cache(client_id):
    global MEMORY_CACHE
    import msal
    if sys.platform == 'win32':
        from msal_extensions import FilePersistenceWithDataProtection, PersistedTokenCache
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # DPAPI protects the cache for the current Windows user; no plaintext fallback.
        return PersistedTokenCache(FilePersistenceWithDataProtection(str(cache_path(client_id))))
    if MEMORY_CACHE is None:
        MEMORY_CACHE = msal.SerializableTokenCache()
    return MEMORY_CACHE


def client(client_id):
    import msal
    return msal.PublicClientApplication(client_id,
        authority='https://login.microsoftonline.com/consumers', token_cache=token_cache(client_id))


def profile_details(account, xbox_result):
    if not xbox_result or 'access_token' not in xbox_result:
        return None
    from .minecraft_profile import get_minecraft_profile, render_skin_bust
    profile, token = get_minecraft_profile(xbox_result['access_token'])
    details = {'display_name': profile['name'], 'minecraft_name': profile['name'],
               'minecraft_id': profile['id'], 'minecraft_token': token,
               'username': account.get('username', '')}
    try:
        details['skin_bust'] = render_skin_bust(profile)
    except Exception as exc:
        details['skin_error'] = str(exc)
    save_settings(account_id=account.get('home_account_id', ''))
    return details


def restore_session(client_id):
    if not client_id:
        return None
    with AUTH_LOCK:
        app = client(client_id)
        accounts = app.get_accounts()
        selected = load_settings().get('account_id')
        account = next((a for a in accounts if a.get('home_account_id') == selected), None)
        if account is None:
            return None
        result = app.acquire_token_silent(scopes=['XboxLive.signin'], account=account)
        # MSAL renews expired Microsoft tokens; exchange again for a fresh game token.
        return profile_details(account, result)


def sign_in(client_id):
    with AUTH_LOCK:
        app = client(client_id)
        result = app.acquire_token_interactive(scopes=['User.Read'], prompt='select_account')
        if 'access_token' not in result:
            raise RuntimeError('No se pudo iniciar sesión en Microsoft. Vuelve a intentarlo.')
        claims = result.get('id_token_claims') or {}
        accounts = app.get_accounts(username=claims.get('preferred_username'))
        if not accounts:
            accounts = app.get_accounts()
        account = next((a for a in accounts if a.get('local_account_id') == claims.get('oid')), accounts[0] if accounts else {})
        xbox = app.acquire_token_silent(scopes=['XboxLive.signin'], account=account)
        if not xbox or 'access_token' not in xbox:
            xbox = app.acquire_token_interactive(scopes=['XboxLive.signin'],
                login_hint=account.get('username'), prompt='select_account')
            xbox_claims = xbox.get('id_token_claims') or {}
            if account.get('local_account_id') and xbox_claims.get('oid') and account['local_account_id'] != xbox_claims['oid']:
                raise RuntimeError('Selecciona la misma cuenta Microsoft en ambas pantallas.')
        details = profile_details(account, xbox)
        if details is None:
            raise RuntimeError('Microsoft necesita que vuelvas a iniciar sesión para autorizar Xbox Live.')
        return details


def sign_out(client_id):
    global MEMORY_CACHE
    with AUTH_LOCK:
        if sys.platform == 'win32' and client_id:
            from msal_extensions import CrossPlatLock
            path = cache_path(client_id)
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with CrossPlatLock(str(path) + '.lockfile'):
                path.unlink(missing_ok=True)
        MEMORY_CACHE = None
        save_settings(account_id='')

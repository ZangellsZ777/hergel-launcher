"""Internal event feed with the bundled catalog available when offline."""
from .core import load_catalog as read_catalog
from .updater import APP_ROOT, update_config


def load_catalog(source=None):
    config = update_config()
    if config:
        url = config['feed_url'].rsplit('/', 1)[0] + '/catalog.json'
        try:
            return read_catalog(url)
        except (OSError, ValueError):
            pass
    return read_catalog(str(APP_ROOT / 'examples' / 'catalog.json'))

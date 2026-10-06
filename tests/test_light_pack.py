import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from hergel.pack import install_bundle

class Response(io.BytesIO):
    def geturl(self):
        return 'https://release-assets.githubusercontent.com/verified'

class LightPackTests(unittest.TestCase):
    def fixture(self):
        content = b'event-mod'
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as archive:
            archive.writestr('mods/event.jar', content)
        data = raw.getvalue()
        meta = {'archive': 'hormiguero.zip',
                'url': 'https://github.com/ZangellsZ777/hergel-launcher/releases/download/event-assets-v1/Hormiguero-Paquete-Jugadores.zip',
                'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                'files': [{'path': 'mods/event.jar', 'size': len(content),
                           'sha256': hashlib.sha256(content).hexdigest()}]}
        return content, data, meta

    def test_initial_install_without_bundled_zip_reuses_cache(self):
        content, data, meta = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = root/'packs'
            manifests.mkdir()
            (manifests/'hormiguero.json').write_text(json.dumps(meta))
            pack = {'bundle': 'hormiguero'}
            with patch('hergel.pack.PACKS', manifests), patch('hergel.pack.DATA_DIR', root/'data'):
                with patch('urllib.request.urlopen', return_value=Response(data)) as request:
                    install_bundle(pack, root/'instance')
                    self.assertEqual(request.call_count, 1)
                    self.assertEqual(request.call_args.args[0].full_url, meta['url'])
                self.assertEqual((root/'instance/mods/event.jar').read_bytes(), content)
                self.assertFalse((manifests/'hormiguero.zip').exists())
                with patch('urllib.request.urlopen', side_effect=AssertionError('Descarga duplicada')):
                    install_bundle(pack, root/'instance')

    def test_corrupt_download_is_not_installed_and_can_be_retried(self):
        content, data, meta = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('hergel.pack.PACKS', root/'packs'), patch('hergel.pack.DATA_DIR', root/'data'):
                with patch('urllib.request.urlopen', return_value=Response(b'x'*len(data))):
                    with self.assertRaises(ValueError):
                        install_bundle({'package': meta}, root/'instance')
                self.assertFalse((root/'instance/mods/event.jar').exists())
                self.assertEqual(list((root/'data/downloads').iterdir()), [])
                with patch('urllib.request.urlopen', return_value=Response(data)):
                    install_bundle({'package': meta}, root/'instance')
                self.assertEqual((root/'instance/mods/event.jar').read_bytes(), content)

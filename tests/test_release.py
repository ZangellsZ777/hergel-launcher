import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from hergel import updater
from hergel.core import load_catalog
from hergel.event_catalog import load_catalog as event_catalog
from hergel.pack import PACKS, bundle_data, install_bundle, validate_remote_package, fetch_package

class Response(io.BytesIO):
    def geturl(self):
        return 'https://release-assets.githubusercontent.com/verified'

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.config = updater.update_config()
        self.release = {'schema':1, 'version':'0.21.0', 'minimum_supported':'0.0.0',
            'installer_url':f'https://github.com/{self.config["repository"]}/releases/download/v0.21.0/Hergel-Launcher-Instalador.exe',
            'sha256':hashlib.sha256(b'installer').hexdigest(), 'size':9, 'notes':'Prueba'}

    def test_version_and_required_behavior(self):
        for minimum, required in [('0.0.0',False),('0.21.0',True)]:
            release = dict(self.release,minimum_supported=minimum)
            with patch('urllib.request.urlopen',return_value=Response(json.dumps(release).encode())):
                self.assertEqual(updater.check_update(self.config)['required'],required)
        with patch('urllib.request.urlopen',return_value=Response(json.dumps(dict(self.release,version=updater.VERSION)).encode())):
            self.assertIsNone(updater.check_update(self.config))

    def test_untrusted_installer_is_rejected(self):
        with self.assertRaises(ValueError):
            updater.validate_release(dict(self.release,installer_url='https://example.com/installer.exe'),self.config)
        with self.assertRaises(ValueError):
            updater.validate_release(dict(self.release,minimum_supported='1.0.0'),self.config)

    def test_corrupt_download_is_never_saved(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(updater,'DATA_DIR',Path(directory)), patch('urllib.request.urlopen',return_value=Response(b'corrupted')):
            with self.assertRaises(ValueError):
                updater.download_update(self.release)
            self.assertEqual(list((Path(directory)/'updates').iterdir()),[])

    def test_valid_download_can_be_reused_offline(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(updater,'DATA_DIR',Path(directory)):
            with patch('urllib.request.urlopen',return_value=Response(b'installer')):
                installer = updater.download_update(self.release)
            with patch('urllib.request.urlopen',side_effect=AssertionError('No debería descargar de nuevo')):
                self.assertEqual(updater.download_update(self.release),installer)

    def test_event_feed_falls_back_offline(self):
        with patch('hergel.event_catalog.read_catalog',side_effect=[OSError('Sin conexión'),{'schema':1,'packs':[]}]) as read:
            self.assertEqual(event_catalog()['packs'],[])
            self.assertIn('/releases/latest/download/catalog.json',read.call_args_list[0].args[0])

    def test_bundle_contents_and_personal_settings(self):
        pack = load_catalog(str(PACKS.parent/'examples/catalog.json'))['packs'][0]
        meta = bundle_data(pack)
        with zipfile.ZipFile(PACKS/meta['archive']) as archive:
            self.assertEqual(set(archive.namelist()),{e['path'] for e in meta['files']})
            for entry in meta['files']:
                data = archive.read(entry['path'])
                self.assertEqual(len(data),entry['size'])
                self.assertEqual(hashlib.sha256(data).hexdigest(),entry['sha256'])
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)/'instance'
            install_bundle(pack,folder)
            options = folder/'options.txt'
            options.write_text('personal-options')
            (folder/'.hergel-install.json').write_text(json.dumps({'files':meta['files']}))
            install_bundle(pack,folder)
            self.assertEqual(options.read_text(),'personal-options')

    def test_remote_catalog_reuses_matching_bundled_pack(self):
        meta = json.loads((PACKS.parent/'pack-source.json').read_text())
        with patch('urllib.request.urlopen',side_effect=AssertionError('Descarga duplicada')):
            self.assertEqual(fetch_package(meta,lambda message:None,lambda *args:None),PACKS/'hormiguero.zip')

    def test_package_cannot_escape_instance(self):
        package = {'url':'https://example.com/pack.zip','size':1,'sha256':'0'*64,
            'files':[{'path':'../secret.txt','size':1,'sha256':'0'*64}]}
        with self.assertRaises(ValueError):
            validate_remote_package(package)

if __name__ == '__main__':
    unittest.main()

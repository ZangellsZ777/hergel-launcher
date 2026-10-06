import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from hergel.game import launch_game


class GameLaunchTests(unittest.TestCase):
    def test_windows_starts_java_without_console_and_keeps_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            java = folder / 'java.exe'
            java.touch()
            command = [str(java), '-version']
            library = SimpleNamespace(
                runtime=SimpleNamespace(get_executable_path=lambda *args: str(java)),
                command=SimpleNamespace(get_minecraft_command=lambda *args: command))
            account = dict(minecraft_name='Player', minecraft_id='test', minecraft_token='test')
            with patch.dict(sys.modules, {'minecraft_launcher_lib': library}), \
                 patch('hergel.game.sys.platform', 'win32'), \
                 patch('hergel.game.subprocess.CREATE_NO_WINDOW', 0x08000000, create=True), \
                 patch('hergel.game.subprocess.Popen') as popen:
                result = launch_game(folder, '1.20.1', account)
                self.assertIs(result, popen.return_value)
                args, options = popen.call_args
                self.assertEqual(args[0], command)
                self.assertEqual(options['creationflags'], 0x08000000)
                self.assertEqual(options['stdin'], -3)
                self.assertEqual(options['stderr'], -2)
                self.assertEqual(Path(options['stdout'].name), folder / 'logs/hergel-launch.log')
                self.assertTrue((folder / 'logs/hergel-launch.log').is_file())

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import server


class TrashTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.src = self.base / 'a "quoted" file.txt'
        self.src.write_text('duplicate')
        self.item = dict(id=7, path=str(self.src), trashable=True,
                         snapshot=server.file_snapshot(self.src.stat()))
        server.state.update(phase='ready', folder=str(self.base), plan=[self.item])
        self.run = patch.object(server.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stderr='')).start()
        self.addCleanup(patch.stopall)

    def test_success_passes_literal_path_and_removes_only_target(self):
        server.state['plan'].append(dict(id=8))
        self.assertEqual(server.trash_file(7), {'trashed': 1})
        self.assertEqual(self.run.call_args.args[0][-1], str(self.src))
        self.assertEqual(server.state['plan'], [dict(id=8)])

    def test_changed_file_is_rejected(self):
        self.src.write_text('changed contents')
        with self.assertRaises(ValueError):
            server.trash_file(7)
        self.run.assert_not_called()

    def test_unknown_or_ineligible_id_is_rejected(self):
        with self.assertRaises(ValueError):
            server.trash_file(99)
        self.item['trashable'] = False
        with self.assertRaises(ValueError):
            server.trash_file(7)
        self.run.assert_not_called()

    def test_symlink_is_rejected(self):
        other = self.base / 'keep.txt'
        other.write_text('keep')
        self.src.unlink()
        self.src.symlink_to(other)
        with self.assertRaises(ValueError):
            server.trash_file(7)
        self.run.assert_not_called()
        self.assertEqual(other.read_text(), 'keep')

    def test_outside_folder_is_rejected(self):
        server.state['folder'] = str(self.base / 'other')
        with self.assertRaises(ValueError):
            server.trash_file(7)
        self.run.assert_not_called()

    def test_finder_failure_preserves_preview(self):
        self.run.return_value = SimpleNamespace(returncode=1, stderr='Not authorized')
        with self.assertRaisesRegex(ValueError, 'Not authorized'):
            server.trash_file(7)
        self.assertEqual(server.state['plan'], [self.item])

    def test_busy_scan_is_rejected(self):
        server.state['phase'] = 'listing'
        with self.assertRaises(ValueError):
            server.trash_file(7)
        self.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

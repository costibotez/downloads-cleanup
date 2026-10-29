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

    def second_item(self):
        path = self.base / 'second.txt'
        path.write_text('second')
        item = dict(id=8, path=str(path), name=path.name, trashable=True,
                    snapshot=server.file_snapshot(path.stat()))
        server.state['plan'].append(item)
        return item

    def test_batch_success_deduplicates_and_preserves_unselected(self):
        other = self.second_item()
        result = server.trash_files([7, 7])
        self.assertEqual(result, {'trashed': 1, 'trashedIds': [7], 'errors': []})
        self.assertEqual(server.state['plan'], [other])
        self.assertEqual(self.run.call_count, 1)

    def test_batch_moves_multiple_files(self):
        self.second_item()
        result = server.trash_files([7, 8])
        self.assertEqual(result['trashedIds'], [7, 8])
        self.assertEqual(server.state['plan'], [])

    def test_batch_continues_after_changed_file(self):
        self.second_item()
        self.src.write_text('changed')
        result = server.trash_files([7, 8])
        self.assertEqual(result['trashedIds'], [8])
        self.assertEqual(result['errors'][0]['id'], 7)
        self.assertEqual(server.state['plan'], [self.item])

    def test_batch_reports_finder_failure(self):
        other = self.second_item()
        self.run.side_effect = [SimpleNamespace(returncode=0, stderr=''),
                                SimpleNamespace(returncode=1, stderr='Not authorized')]
        result = server.trash_files([7, 8])
        self.assertEqual(result['trashed'], 1)
        self.assertIn('Not authorized', result['errors'][0]['error'])
        self.assertEqual(server.state['plan'], [other])

    def test_batch_rejects_invalid_requests_before_mutation(self):
        for ids in [[], None, '7', [7, '8'], [True], [[7]]]:
            with self.assertRaises(ValueError):
                server.trash_files(ids)
        self.run.assert_not_called()

    def test_batch_unknown_and_ineligible_ids_remain_untouched(self):
        self.item['trashable'] = False
        result = server.trash_files([7, 99])
        self.assertEqual(result['trashed'], 0)
        self.assertEqual(len(result['errors']), 2)
        self.assertEqual(server.state['plan'], [self.item])
        self.run.assert_not_called()


    def test_busy_scan_is_rejected(self):
        server.state['phase'] = 'listing'
        with self.assertRaises(ValueError):
            server.trash_file(7)
        self.run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import server
import sorter
from watcher import Watcher


class RoadmapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'downloads'
        self.folder.mkdir()
        self.data = self.root / 'data'
        for name, value in [('HISTORY', self.data / 'history'), ('CONFIG_FILE', self.data / 'config.json'), ('watcher', Watcher())]:
            patch.object(server, name, value).start()
        self.addCleanup(patch.stopall)
        server.save_json(server.CONFIG_FILE, dict(server.DEFAULT_CONFIG, folder=str(self.folder)))
        server.state.update(phase='idle', plan=None, folder=str(self.folder), error=None)

    def entry(self, name='123456.pdf', content='sample'):
        p = self.folder / name
        p.write_text(content)
        os.utime(p, (time.time() - 500, time.time() - 500))
        return dict(path=str(p), name=name, st=p.stat(), is_dir=False)

    def plan(self, e, analysis=None, **options):
        return sorter.build_plan([e], {e['path']: analysis or {}}, [], dict(rename=True, **options), {})[0]

    def test_pdf_name_and_document_date(self):
        e = self.entry()
        a = dict(text='Invoice\nSupplier: Engie\nInvoice date: 23.05.2023\nAmount due: 30')
        p = self.plan(e, a, dateFolders=True)
        self.assertEqual(p['newName'], 'Invoice – Engie – 2023-05-23.pdf')
        self.assertEqual(p['dateFolder'], '2023/05')

    def test_meaningful_name_and_rename_off(self):
        a = dict(text='Invoice\nDate: 2023-05-23')
        e = self.entry('My invoice.pdf')
        self.assertEqual(self.plan(e, a)['newName'], e['name'])
        e = self.entry()
        p = sorter.build_plan([e], {e['path']: a}, [], {'rename': False}, {})[0]
        self.assertEqual(p['newName'], e['name'])

    def test_unknown_pdf_and_invalid_date(self):
        e = self.entry()
        self.assertEqual(self.plan(e, dict(text='Random text'))['newName'], e['name'])
        self.assertIsNone(sorter.document_date(dict(text='Invoice date: 31.02.2023')))

    def test_capture_date_and_clutter_exclusion(self):
        e = self.entry('IMG_1234.jpg')
        self.assertEqual(self.plan(e, dict(taken='2021:04:05 00:00:00'), dateFolders=True)['dateFolder'], '2021/04')
        e = self.entry('empty.txt', '')
        self.assertEqual(self.plan(e, dateFolders=True)['dateFolder'], '')

    def test_nested_move_collision_and_undo(self):
        e = self.entry('notes.txt')
        p = self.plan(e, dateFolders=True)
        server.state.update(plan=[p], phase='ready')
        target = self.folder / p['category'] / p['dateFolder']
        target.mkdir(parents=True)
        (target / e['name']).write_text('existing')
        result = server.apply_moves(str(self.folder), [{'id': p['id']}], automatic=True)
        self.assertEqual(result['moved'], 1)
        self.assertEqual((target / 'notes 2.txt').read_text(), 'sample')
        h = server.history()[0]
        self.assertTrue(h['automatic'])
        self.assertEqual(server.undo(h['id'])['restored'], 1)
        self.assertEqual(Path(e['path']).read_text(), 'sample')
        self.assertEqual((target / e['name']).read_text(), 'existing')
        self.assertFalse(server.config()['watch'])

    def test_traversal_and_symlink_destinations_rejected(self):
        e = self.entry('notes.txt')
        p = self.plan(e)
        for category in ['../escape', '/tmp/escape', 'a/../../escape', 'a//b']:
            server.state.update(plan=[p], phase='ready')
            self.assertEqual(server.apply_moves(str(self.folder), [{'id': p['id'], 'category': category}])['moved'], 0)
        (self.folder / 'link').symlink_to(self.root, target_is_directory=True)
        server.state.update(plan=[p], phase='ready')
        self.assertEqual(server.apply_moves(str(self.folder), [{'id': p['id'], 'category': 'link/escape'}])['moved'], 0)
        self.assertTrue(Path(e['path']).exists())

    def test_watch_baseline_stability_and_changes(self):
        old = self.entry('existing.txt')
        w = Watcher()
        w.reset(str(self.folder), [old])
        new = self.entry('new.txt')
        now = time.time()
        self.assertEqual(w.candidates([old, new], now=now), [])
        self.assertEqual(w.candidates([old, new], now=now + 119), [])
        self.assertEqual(w.candidates([old, new], now=now + 121), [new])
        changed = self.entry('new.txt', 'updated')
        self.assertEqual(w.candidates([old, changed], now=now + 122), [])
        w.acknowledge([changed])
        self.assertEqual(w.candidates([old, changed], now=now + 500), [])

    def test_watch_sorts_new_files_only_and_records_history(self):
        self.entry('existing.txt')
        cfg = dict(server.config(), watch=True)
        server.save_json(server.CONFIG_FILE, cfg)
        server.watch_tick()
        new = self.entry('new.txt')
        server.watch_tick()
        with patch('watcher.time.time', return_value=time.time() + 121), patch.object(server, 'analyze', return_value={}):
            server.watch_tick()
        self.assertTrue((self.folder / 'existing.txt').exists())
        self.assertFalse(Path(new['path']).exists())
        self.assertTrue((self.folder / 'Documents/Word & text/new.txt').exists())
        self.assertTrue(server.history()[0]['automatic'])

    def test_watch_keeps_modified_existing_files(self):
        old = self.entry('existing.txt')
        w = Watcher()
        w.reset(str(self.folder), [old])
        changed = self.entry('existing.txt', 'edited')
        now = time.time()
        self.assertEqual(w.candidates([changed], now=now), [])
        self.assertEqual(w.candidates([changed], now=now + 500), [])

    def test_watch_failure_disables_setting(self):
        server.save_json(server.CONFIG_FILE, dict(server.config(), watch=True))
        with patch.object(server, 'watch_tick', side_effect=OSError('Permission denied')), patch.object(server.time, 'sleep', side_effect=StopIteration):
            with self.assertRaises(StopIteration):
                server.watch_loop()
        self.assertFalse(server.config()['watch'])
        self.assertIn('Permission denied', server.watcher.message)


    def test_watch_pauses_for_manual_preview(self):
        server.save_json(server.CONFIG_FILE, dict(server.config(), watch=True))
        server.state['phase'] = 'ready'
        with patch.object(server, 'scan') as scan:
            server.watch_tick()
        scan.assert_not_called()
        self.assertIn('paused', server.watcher.message)


if __name__ == '__main__':
    unittest.main()

"""History keeps distinct exchanges without pretending to have transcripts."""
import json
from pathlib import Path
import tempfile
import unittest

from m10_history import append_history, load_history


class HistoryTests(unittest.TestCase):
    def test_voice_and_reply_survive_restart_and_duplicate_reply_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.json'
            append_history(path, 'voice', 'Voice note', 'Five-second voice note sent to Muse.', 100, 'voice-1')
            append_history(path, 'reply', 'Kit', 'The board is online.', 110, 'reply-1')
            self.assertFalse(append_history(path, 'reply', 'Kit', 'The board is online.', 110, 'reply-1'))
            self.assertEqual([item['kind'] for item in load_history(path)], ['voice', 'reply'])
            self.assertEqual(load_history(path)[1]['text'], 'The board is online.')
            self.assertEqual(len(json.loads(path.read_text())), 2)

    def test_only_latest_fifty_items_are_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.json'
            for index in range(55):
                append_history(path, 'reply', 'Kit', str(index), index, str(index))
            items = load_history(path)
            self.assertEqual((len(items), items[0]['text'], items[-1]['text']), (50, '5', '54'))

    def test_imported_old_display_has_explicit_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.json'
            append_history(path, 'reply', 'Old status', 'Saved screen text',
                           110, 'old-1', origin='legacy_import')
            self.assertEqual(load_history(path)[0]['origin'], 'legacy_import')


if __name__ == '__main__':
    unittest.main()

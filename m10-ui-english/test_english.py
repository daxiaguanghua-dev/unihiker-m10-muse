"""Focused checks for the English-only behavior changed by localization."""
import unittest

from muse_connection import classify
from muse_ui_model import clean_text, paginate_message, screen_state


class EnglishVariantTests(unittest.TestCase):
    def test_direct_wifi_is_valid_without_a_local_proxy(self):
        status, title, _ = classify(True, None, True, False, True)
        self.assertEqual((status, title), ('checking', 'Device status unavailable'))

    def test_no_network_is_reported_as_offline(self):
        status, title, _ = classify(True, None, False, False, False)
        self.assertEqual((status, title), ('offline', 'Wi-Fi disconnected'))

    def test_agent_failure_text_remains_a_failure(self):
        data = {'source': 'm10_agent', 'text': 'Voice send failed\nCheck connection, then retry'}
        self.assertEqual(screen_state(data, 'work'), 'failed')

    def test_reply_text_is_not_mistaken_for_a_voice_state(self):
        data = {'source': 'Muse device tool', 'text': 'Recording is complete. Here is the result.'}
        self.assertEqual(screen_state(data, 'work'), 'message')

    def test_recording_finished_is_sending_not_another_countdown(self):
        data = {'source': 'm10_agent', 'text': 'Recording finished\nSending to Muse...'}
        self.assertEqual(screen_state(data, 'work'), 'sending')

    def test_active_recording_still_has_one_countdown(self):
        data = {'source': 'm10_agent', 'text': 'Recording for 5 seconds\nSpeak to the board'}
        self.assertEqual(screen_state(data, 'work'), 'recording')

    def test_reply_paging_keeps_a_short_status_line_together(self):
        lines = ['a' * 8] * 5 + ['b' * 16]
        pages = paginate_message('\n'.join(lines), len, 10, 6)
        self.assertEqual(pages, [['a' * 8] * 5, ['b' * 10, 'b' * 6]])

    def test_level_unit_does_not_wrap_away_from_its_number(self):
        self.assertIn('-39.8dBFS', clean_text('声级 -39.8 dBFS'))


if __name__ == '__main__':
    unittest.main()

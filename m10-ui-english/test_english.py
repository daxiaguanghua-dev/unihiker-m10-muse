"""Focused checks for the English-only behavior changed by localization."""
import unittest

from muse_connection import classify
from muse_ui_model import screen_state


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


if __name__ == '__main__':
    unittest.main()

"""Focused check: reasoning fallback prevents empty chat bubbles."""
import unittest

from runtime.server.handlers import _message_text


class MessageTextTests(unittest.TestCase):
    def test_prefers_content(self):
        self.assertEqual(_message_text({"content": "hi", "reasoning_content": "think"}), "hi")

    def test_fallback_to_reasoning_when_empty(self):
        self.assertEqual(_message_text({"content": "", "reasoning_content": "deep thought"}), "deep thought")
        self.assertEqual(_message_text({"content": "   ", "reasoning_content": "deep thought"}), "deep thought")

    def test_empty_when_both_empty(self):
        self.assertEqual(_message_text({"content": ""}), "")
        self.assertEqual(_message_text({}), "")
        self.assertEqual(_message_text(None), "")

if __name__ == "__main__":
    unittest.main()

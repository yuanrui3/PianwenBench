import unittest
from unittest.mock import Mock

from pianwen.clients import GeminiClient


class GeminiClientTests(unittest.TestCase):
    def test_mock_request_disables_tools_and_logs_settings(self):
        transport = Mock(return_value="fixture response")
        client = GeminiClient(model="mock-gemini", transport=transport)

        with self.assertLogs("pianwen.clients.gemini", level="INFO") as log:
            result = client.generate("fixture prompt", temperature=0.2, max_tokens=128)

        self.assertEqual(result, "fixture response")
        transport.assert_called_once_with(
            model="mock-gemini",
            prompt="fixture prompt",
            temperature=0.2,
            max_tokens=128,
            tools=(),
        )
        self.assertEqual(len(log.records), 1)
        message = log.records[0].getMessage()
        for setting in (
            "model='mock-gemini'",
            "temperature=0.2",
            "max_tokens=128",
            "closed_book=true",
            "tools=[]",
            "web_search=false",
            "retrieval=false",
        ):
            self.assertIn(setting, message)
        self.assertNotIn("fixture prompt", message)
        self.assertNotIn("fixture response", message)

    def test_failed_request_still_logs_the_attempt(self):
        transport = Mock(side_effect=RuntimeError("fixture failure"))
        client = GeminiClient(model="mock-gemini", transport=transport)

        with self.assertLogs("pianwen.clients.gemini", level="INFO") as log:
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                client.generate("fixture prompt", temperature=0.0, max_tokens=64)

        self.assertEqual(len(log.records), 1)
        self.assertIn("max_tokens=64", log.records[0].getMessage())

"""Run one example Gemini call with an offline transport."""

import logging

from pianwen.clients import GeminiClient


def mock_transport(**settings):
    return "Mock Gemini response"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = GeminiClient(model="mock-gemini", transport=mock_transport)
    print(client.generate("Offline connectivity check.", temperature=0, max_tokens=32))

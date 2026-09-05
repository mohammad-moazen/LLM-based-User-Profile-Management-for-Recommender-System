"""Tests for the backend-agnostic local LLM HTTP client."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pure_recommender.llm.client import OpenAICompatibleLLMClient


class _MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003 - inherited API name
        return

    def _write_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - HTTP server API
        if self.path == "/v1/models":
            self._write_json(
                {
                    "object": "list",
                    "data": [
                        {"id": "model-a", "object": "model"},
                        {"id": "model-b", "object": "model"},
                    ],
                }
            )
            return
        self._write_json({"error": "not found"}, status=404)

    def do_POST(self):  # noqa: N802 - HTTP server API
        if self.path != "/v1/chat/completions":
            self._write_json({"error": "not found"}, status=404)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        request_payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        self._write_json(
            {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": request_payload["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "LOCAL_LLM_OK"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            }
        )


class LLMClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _MockHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.client = OpenAICompatibleLLMClient(f"http://{host}:{port}/v1", timeout_seconds=5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_list_models(self):
        self.assertEqual(self.client.list_models(), ["model-a", "model-b"])

    def test_chat_completion(self):
        response = self.client.chat_completion(
            model="model-a",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.0,
            max_tokens=8,
            seed=42,
        )
        self.assertEqual(response.content, "LOCAL_LLM_OK")
        self.assertEqual(response.model, "model-a")
        self.assertEqual(response.usage["total_tokens"], 13)


if __name__ == "__main__":
    unittest.main()

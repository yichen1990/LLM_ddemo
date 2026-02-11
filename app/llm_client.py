import requests
from typing import Dict, List

class LLMClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.1, timeout_s: int = 120) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": temperature},
            "stream": False,
        }
        r = requests.post(url, json=payload, timeout=timeout_s)
        r.raise_for_status()
        return r.json()["message"]["content"]

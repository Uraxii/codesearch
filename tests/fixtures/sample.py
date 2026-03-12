import os
from typing import Optional


def greet(name: str) -> str:
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    return a + b


class HttpClient:
    def fetch(self, url: str) -> bytes:
        pass

    def post(self, url: str, data: str) -> bytes:
        pass


class WebRequest:
    def send(self, endpoint: str) -> None:
        pass


def use_web_request(req: WebRequest) -> None:
    req.send("/api")


def use_http_client(client: HttpClient) -> None:
    client.fetch("https://example.com")

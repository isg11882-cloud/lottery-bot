import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class HttpClient:
    def __init__(self):
        self.session = requests.Session()
        self.connect_timeout = float(os.environ.get("LOTTO_HTTP_CONNECT_TIMEOUT", "45"))
        self.read_timeout = float(os.environ.get("LOTTO_HTTP_READ_TIMEOUT", "60"))
        self.default_timeout = (self.connect_timeout, self.read_timeout)

        retries = Retry(
            total=int(os.environ.get("LOTTO_HTTP_RETRIES", "5")),
            connect=int(os.environ.get("LOTTO_HTTP_CONNECT_RETRIES", os.environ.get("LOTTO_HTTP_RETRIES", "5"))),
            read=int(os.environ.get("LOTTO_HTTP_READ_RETRIES", "3")),
            backoff_factor=float(os.environ.get("LOTTO_HTTP_BACKOFF", "1.5")),
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def __del__(self):
        self.session.close()

    def post(self, url: str, headers: dict = None, data: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        res = self.session.post(url, headers=session_headers, data=data, timeout=self.default_timeout, allow_redirects=True)
        res.raise_for_status()
        return res

    def get(self, url: str, headers: dict = None, params: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        res = self.session.get(url, headers=session_headers, params=params, timeout=self.default_timeout)
        res.raise_for_status()
        return res

class HttpClientSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if HttpClientSingleton._instance is None:
            HttpClientSingleton._instance = HttpClient()
        return HttpClientSingleton._instance

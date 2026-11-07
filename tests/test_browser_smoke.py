"""Smoke test of the review desk in a real browser: headless Edge or Chrome, found on this computer; the test is skipped when there is none.

The other web tests check the server and the files it serves. This one loads the page, opens a finished case and each of the seven tabs, waits
for the words each tab must show (a tab that stays empty, stays on "Loading..." or shows a load error fails), and fails on any uncaught page
error, any console error and anything the content-security policy blocks. The browser is driven over its DevTools port with a plain socket
and the standard library: no automation package is installed for it. It shows that the page runs and draws its tabs; it says nothing about
how the page looks, or about any browser but the one it finds."""
import base64
import http.client
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import uvicorn
from fastapi.testclient import TestClient

from docforensics.dossier import CLASS_LABEL
from docforensics.web.app import HOST, create_app
from tests.helpers import d1_edited_statement, pdf_bytes

# What each tab must show for the case built below (an edited statement and a plain PDF): words taken from a real run of the page.
EXPECTED = {
    "documents": ("statement.pdf", "note.pdf", "Extracted fields", "account_holder"),
    "findings": ("F-002", "F-003", "F-005", *CLASS_LABEL.values()),
    "clusters": ("F-005", "AI reading of the case (inference)"),
    "relationships": ("Entities", "Priya D. Joshi", "TST-3095328386"),
    "audit": ("Hash chain intact", "Signed:", "case_created"),
    "capabilities": ("Implemented", "Partial", "Unsupported"),
    "dossier": ("Reviewer decisions", "statement_balance", "Dismissed"),
}


def find_browser() -> str | None:
    for name in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chrome"):
        if found := shutil.which(name):
            return found
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData"):
        for rel in ("Microsoft/Edge/Application/msedge.exe", "Google/Chrome/Application/chrome.exe"):
            if os.environ.get(var) and (path := Path(os.environ[var]) / rel).is_file():
                return str(path)
    return None


class Page:
    """One page of the browser, spoken to over the DevTools protocol (JSON over a WebSocket, written out here: the handshake, masked
    text frames out, unmasked frames in). Events that arrive while a command waits for its answer are kept in `events`."""

    def __init__(self, port: int, path: str):
        self.sock = socket.create_connection((HOST, port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {HOST}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while not head.endswith(b"\r\n\r\n"):
            head += self.sock.recv(1)  # one byte at a time, so that no byte of the first frame is read with the headers
        assert b" 101 " in head.split(b"\r\n")[0], head
        self.count, self.events = 0, []

    def _read(self, n: int) -> bytes:
        out = b""
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise ConnectionError("the browser closed the connection")
            out += chunk
        return out

    def _message(self) -> dict:
        text = b""
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            payload = self._read(n)
            if b1 & 0x0F == 8:
                raise ConnectionError("the browser closed the connection")
            if b1 & 0x0F in (0, 1, 2):  # a text frame, or a continuation of one; pings are not answered, the browser sends none
                text += payload
                if b1 & 0x80:
                    return json.loads(text)

    def call(self, method: str, **params) -> dict:
        self.count += 1
        body = json.dumps({"id": self.count, "method": method, "params": params}).encode()
        n, mask = len(body), os.urandom(4)
        size = bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536 else bytes([0x80 | 127]) + struct.pack(">Q", n)
        self.sock.sendall(b"\x81" + size + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(body)))
        while True:
            m = self._message()
            if m.get("id") != self.count:
                self.events.append(m)
                continue
            assert "error" not in m, f"{method}: {m['error']}"
            return m["result"]

    def js(self, expression: str):
        r = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)  # a promise is waited for
        assert "exceptionDetails" not in r, r["exceptionDetails"]
        return r["result"].get("value")

    def wait_for(self, expression: str, seconds: float = 30):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.js(expression):
                return
            time.sleep(0.1)
        raise AssertionError(f"still false after {seconds} s: {expression}")

    def problems(self) -> list[str]:
        """What the page did wrong so far: an uncaught error, a console error, a request the policy or the server refused."""
        self.js("0")  # a round trip, so the events sent before it have been read
        found = []
        for m in self.events:
            p = m.get("params", {})
            if m["method"] == "Runtime.exceptionThrown":
                d = p["exceptionDetails"]
                found.append(f"uncaught: {d.get('exception', {}).get('description') or d['text']}")
            elif m["method"] == "Runtime.consoleAPICalled" and p["type"] in ("error", "assert"):
                found.append("console." + p["type"] + ": " + " ".join(str(a.get("value", a.get("description", ""))) for a in p["args"]))
            elif m["method"] == "Log.entryAdded" and p["entry"]["level"] == "error" and not p["entry"].get("url", "").endswith("/favicon.ico"):
                found.append(f"{p['entry']['source']}: {p['entry']['text']} {p['entry'].get('url', '')}")
        return found


@pytest.fixture(scope="module")
def desk(tmp_path_factory):
    """A finished case (an edited statement and a plain PDF), served by the real app on a free port of this computer."""
    data = tmp_path_factory.mktemp("browser") / "data"
    client = TestClient(create_app(data), base_url="http://127.0.0.1:8000")
    files = [("files", (name, content, "application/octet-stream")) for name, content in (("statement.pdf", d1_edited_statement()), ("note.pdf", pdf_bytes()))]
    cid = client.post("/api/cases", files=files).json()["case_id"]
    end = time.monotonic() + 90
    while client.get(f"/api/cases/{cid}").json()["status"] == "processing":
        assert time.monotonic() < end, "the case did not finish"
        time.sleep(0.2)
    server = uvicorn.Server(uvicorn.Config(create_app(data), host=HOST, port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    end = time.monotonic() + 20
    while not server.started:
        assert time.monotonic() < end, "the server did not start"
        time.sleep(0.05)
    yield f"http://{HOST}:{server.servers[0].sockets[0].getsockname()[1]}", cid
    server.should_exit = True
    thread.join(10)


def close_browser(port: int | None, proc: subprocess.Popen) -> None:
    """Edge starts its browser as a process of its own and the one started here exits at once, so killing that one closes nothing:
    the browser is asked to close through its DevTools port, and the process started here is killed if it is still there."""
    if port is not None:
        try:
            conn = http.client.HTTPConnection(HOST, port, timeout=10)
            conn.request("GET", "/json/version")
            path = urlsplit(json.loads(conn.getresponse().read())["webSocketDebuggerUrl"]).path
            conn.close()
            Page(port, path).call("Browser.close")
        except (OSError, ConnectionError):  # it goes away before it answers, or it is gone already
            pass
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)  # the browser starts helper processes
        else:
            proc.terminate()
    proc.wait(15)


@pytest.fixture(scope="module")
def page():
    exe = find_browser()
    if exe is None:
        pytest.skip("no Edge or Chrome on this computer")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        proc = subprocess.Popen([exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                                 "--remote-debugging-port=0", f"--user-data-dir={profile}", "about:blank"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sock = port = None
        try:
            end = time.monotonic() + 30
            port_file = Path(profile) / "DevToolsActivePort"
            while len(port_file.read_text().split() if port_file.is_file() else []) < 2:
                if proc.poll() not in (None, 0) or time.monotonic() > end:  # Edge's own process exits with 0 once it has started the browser
                    pytest.skip("the browser did not open its DevTools port")
                time.sleep(0.1)
            port = int(port_file.read_text().split()[0])
            path = None
            while path is None:
                conn = http.client.HTTPConnection(HOST, port, timeout=10)
                conn.request("GET", "/json/list")
                pages = [t for t in json.loads(conn.getresponse().read()) if t["type"] == "page"]
                conn.close()
                if pages:
                    path = urlsplit(pages[0]["webSocketDebuggerUrl"]).path
                elif time.monotonic() > end:
                    pytest.skip("the browser opened no page")
                else:
                    time.sleep(0.1)
            sock = Page(port, path)
            for domain in ("Page", "Runtime", "Log"):
                sock.call(f"{domain}.enable")
            yield sock
        finally:
            if sock is not None:
                sock.sock.close()
            close_browser(port, proc)


def test_every_tab_draws_its_content_and_the_page_raises_no_error(desk, page):
    base, cid = desk
    page.call("Page.navigate", url=f"{base}/#{cid}")
    page.wait_for("(document.getElementById('caseline') || {textContent: ''}).textContent.includes('analysis finished')")
    for tab, words in EXPECTED.items():
        page.js(f"document.getElementById('btn-{tab}').click()")
        page.wait_for(f"!document.getElementById('tab-{tab}').hidden")
        for word in words:  # the tabs that fetch their data fill in after the click, so wait for the words and do not sleep
            page.wait_for(f"document.getElementById('tab-{tab}').innerText.includes({json.dumps(word)})", seconds=15)
        text = page.js(f"document.getElementById('tab-{tab}').innerText")
        assert not re.search(r"Loading|could not be (loaded|read)", text), f"the {tab} tab is still waiting or shows an error:\n{text[:600]}"
    time.sleep(1)  # a short last wait, so that an error raised by a timer or a late request of the last tab is seen as well
    assert page.problems() == []


def test_a_finding_opens_with_its_evidence_and_a_reviewer_decision_is_recorded(desk, page):
    base, cid = desk
    page.call("Page.navigate", url=f"{base}/#{cid}/F-003")  # the address of one finding of the case
    page.wait_for("document.getElementById('detail').innerText.includes('F-003: The balance in row 2')")
    page.wait_for("document.querySelector('#page svg rect.ev.sel') !== null")  # its own box is drawn on the page it points to
    href = page.js("document.querySelector('#page svg image').getAttribute('href')")
    assert page.js(f"new Promise((r) => {{ const i = new Image(); i.onload = () => r(i.naturalWidth); i.onerror = () => r(0); i.src = {json.dumps(href)}; }})") > 0
    page.wait_for("(() => { const c = [...document.querySelectorAll('#detail img.crop')]; return c.length > 0 && c.every((i) => i.complete && i.naturalWidth > 0); })()")
    page.js("[...document.querySelectorAll('#detail button')].find((b) => b.textContent === 'Show on page').click()")
    page.wait_for("document.querySelector('#page svg rect.hl') !== null")  # the evidence is marked on the page
    page.js("[...document.querySelectorAll('#detail .actions button')].find((b) => b.textContent === 'Needs verification').click()")
    page.wait_for("document.getElementById('detail').innerText.includes('Status: Needs verification')")
    rows = page.js(f"fetch('/api/cases/{cid}/decisions').then((r) => r.json()).then((d) => d.rows)")  # what the reviewer did is read back from the audit trail
    assert {r["finding"]: r["status"] for r in rows}["F-003"] == "needs_verification"
    time.sleep(1)
    assert page.problems() == []

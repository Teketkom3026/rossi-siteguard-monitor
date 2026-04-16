"""
MonitorEngine — background QThread for site monitoring, threat scanning, SSL checks.
v2.0.0: ProxyHandler({}) bypass fixes 407 = offline bug.
"""
from __future__ import annotations

import logging
import re
import socket
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("SiteGuard.MonitorEngine")

# ---------------------------------------------------------------------------
# Threat patterns — regex + description
# ---------------------------------------------------------------------------
THREAT_PATTERNS = [
    (r'eval\s*\(\s*base64_decode', 'PHP malware — eval(base64_decode)'),
    (r'<script[^>]*>\s*eval\s*\(', 'Suspicious eval() in script'),
    (r'document\.write\s*\(\s*unescape', 'Obfuscated JS — document.write+unescape'),
    (r'iframe[^>]+src=["\'](?:https?:)?//(?!{domain})', 'External hidden iframe'),
    (r'<script[^>]+src=["\']https?://(?!{domain}|cdn\.|ajax\.|fonts\.)', 'External script injection'),
    (r'(?:union\s+select|or\s+1=1|drop\s+table)', 'SQL injection indicator'),
    (r'<script[^>]*>.*?(?:alert|confirm|prompt)\s*\(', 'XSS indicator'),
    (r'crypto(?:miner|night|jacking|\.mine)', 'Cryptominer detected'),
    (r'phishing|credential.?harvest', 'Phishing indicator'),
    (r'\.onion\b', 'Dark web link detected'),
]


class MonitorEngine(QThread):
    """Background monitoring thread — checks sites, scans threats, checks SSL."""

    results_ready = pyqtSignal(dict)

    def __init__(self, domains: List[str], timeout: int = 15,
                 threat_scan: bool = True, scan_every_n: int = 10,
                 parent=None):
        super().__init__(parent)
        self._domains = list(domains)
        self._timeout = timeout
        self._threat_scan = threat_scan
        self._scan_every_n = max(1, scan_every_n)
        self._stop = False
        self._check_counter: Dict[str, int] = {}

    def stop_gracefully(self):
        self._stop = True

    def run(self):
        results: Dict[str, dict] = {}
        for domain in self._domains:
            if self._stop:
                break
            results[domain] = self._check_site(domain)
        if not self._stop:
            self.results_ready.emit(results)

    # ------------------------------------------------------------------
    # Site check — ProxyHandler({}) bypass is CRITICAL
    # ------------------------------------------------------------------
    def _check_site(self, domain: str) -> dict:
        status_code = 0
        response_ms = 0
        is_up = False
        error: Optional[str] = None

        for scheme in ("https", "http"):
            url = f"{scheme}://{domain}"
            try:
                t0 = time.time()
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", "Mozilla/5.0 SiteGuard-Monitor/2.0.0")
                # CRITICAL: bypass system proxy to avoid 407 errors
                handler = urllib.request.ProxyHandler({})
                opener = urllib.request.build_opener(handler)
                with opener.open(req, timeout=self._timeout) as resp:
                    status_code = resp.status
                    response_ms = round((time.time() - t0) * 1000)
                    is_up = True  # ANY response = site is up
                break
            except urllib.error.HTTPError as exc:
                status_code = exc.code
                response_ms = round((time.time() - t0) * 1000)
                is_up = status_code < 500  # 4xx = up, 5xx = error
                break
            except urllib.error.URLError as exc:
                error = str(exc.reason)[:80]
                continue
            except socket.timeout:
                error = "Timeout"
                continue
            except Exception as exc:
                error = str(exc)[:80]
                continue

        # SSL check
        ssl_days = self._check_ssl(domain)

        # Threat scan (only if site is up and every N checks)
        threats: List[dict] = []
        if self._threat_scan and is_up:
            counter = self._check_counter.get(domain, 0) + 1
            self._check_counter[domain] = counter
            if counter % self._scan_every_n == 1 or counter == 1:
                threats = self._scan_threats(domain)

        return {
            "up": is_up,
            "status_code": status_code,
            "response_ms": response_ms,
            "ssl_days": ssl_days,
            "threats": threats,
            "last_check": datetime.now().strftime("%H:%M:%S"),
            "error": error,
        }

    # ------------------------------------------------------------------
    # SSL certificate check
    # ------------------------------------------------------------------
    def _check_ssl(self, domain: str) -> Optional[int]:
        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
                s.settimeout(8)
                s.connect((domain, 443))
                cert = s.getpeercert()
                if cert:
                    not_after = cert.get("notAfter", "")
                    expires_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    return (expires_dt - datetime.utcnow()).days
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Threat scan — fetch HTML and match regex patterns
    # ------------------------------------------------------------------
    def _scan_threats(self, domain: str) -> List[dict]:
        threats = []
        try:
            url = f"https://{domain}"
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "Mozilla/5.0 SiteGuard-Monitor/2.0.0")
            handler = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(handler)
            with opener.open(req, timeout=self._timeout) as resp:
                html = resp.read(500_000).decode("utf-8", errors="ignore")
        except Exception:
            return threats

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for pattern, desc in THREAT_PATTERNS:
            try:
                # Replace {domain} placeholder in pattern
                compiled = pattern.replace("{domain}", re.escape(domain))
                if re.search(compiled, html, re.IGNORECASE | re.DOTALL):
                    threats.append({
                        "type": desc.split("—")[0].split("—")[0].strip(),
                        "desc": desc,
                        "time": now,
                    })
            except Exception:
                continue

        if threats:
            logger.info(f"Threats found on {domain}: {len(threats)}")
        return threats

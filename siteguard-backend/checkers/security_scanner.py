"""
Модуль сканирования безопасности:
- Обнаружение вредоносного кода
- Подозрительные ссылки и файлы
- Внешние атаки (WAF-индикаторы)
- Проверка заголовков безопасности
- Интеграция с VirusTotal API
"""
import asyncio
import aiohttp
import re
import hashlib
import base64
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import logging
logger = logging.getLogger(__name__)
@dataclass
class SecurityThreat:
    threat_type: str           # malware, suspicious_link, suspicious_file,
                                # missing_header, xss, injection, etc.
    severity: str              # critical, high, medium, low, info
    description: str
    location: Optional[str] = None    # URL или элемент где найдена угроза
    details: Optional[str] = None
    recommendation: Optional[str] = None
@dataclass
class SecurityScanResult:
    domain: str
    timestamp: datetime
    overall_score: int = 100       # 0-100, чем выше тем лучше
    threats: List[SecurityThreat] = field(default_factory=list)
    security_headers: Dict[str, bool] = field(default_factory=dict)
    malware_detected: bool = False
    suspicious_links: List[str] = field(default_factory=list)
    suspicious_files: List[str] = field(default_factory=list)
    external_scripts: List[str] = field(default_factory=list)
    has_waf: bool = False
    waf_name: Optional[str] = None
    error_message: Optional[str] = None
class SecurityScanner:
    def __init__(self, virustotal_api_key: Optional[str] = None):
        self.vt_api_key = virustotal_api_key
        # Паттерны вредоносного кода
        self.malware_patterns = [
            # Обфусцированный JavaScript
            r'eval\s*\(\s*unescape\s*\(',
            r'eval\s*\(\s*String\.fromCharCode',
            r'eval\s*\(\s*atob\s*\(',
            r'document\.write\s*\(\s*unescape',
            r'eval\s*\(\s*function\s*\(\s*p\s*,\s*a\s*,\s*c\s*,\s*k\s*,\s*e\s*,\s*[dr]\s*\)',
            # Base64 подозрительный контент
            r'atob\s*\(["\'][A-Za-z0-9+/=]{100,}',
            # Скрытые iframe
            r'<iframe[^>]*style\s*=\s*["\'][^"\']*display\s*:\s*none',
            r'<iframe[^>]*style\s*=\s*["\'][^"\']*visibility\s*:\s*hidden',
            r'<iframe[^>]*width\s*=\s*["\']?0["\']?[^>]*height\s*=\s*["\']?0',
            r'<iframe[^>]*height\s*=\s*["\']?0["\']?[^>]*width\s*=\s*["\']?0',
            # Редиректы на подозрительные домены
            r'window\.location\s*=\s*["\']https?://(?!(?:www\.)?(?:google|yandex|vk|ok)\.',
            r'document\.location\.href\s*=\s*["\']https?://',
            r'window\.location\.replace\s*\(\s*["\']https?://',
            r'meta\s+http-equiv\s*=\s*["\']refresh["\'][^>]*url\s*=\s*https?://',
            # Криптомайнеры
            r'coinhive\.min\.js',
            r'CoinHive\.Anonymous',
            r'crypto-?loot',
            r'coin-?imp',
            r'mineralt',
            r'webmine\.pro',
            # Подозрительные загрузки
            r'\.exe["\'\s>]',
            r'\.scr["\'\s>]',
            r'\.bat["\'\s>]',
            r'\.cmd["\'\s>]',
            r'\.ps1["\'\s>]',
            r'\.vbs["\'\s>]',
            # Подозрительные PHP-паттерны (если видны в HTML)
            r'<\?php\s',
            r'passthru\s*\(',
            r'shell_exec\s*\(',
            r'system\s*\(',
            r'base64_decode\s*\(\s*["\'][A-Za-z0-9+/=]{50,}',
            # WebShell-паттерны
            r'c99shell',
            r'r57shell',
            r'WSO\s+\d',
            r'FilesMan',
            # SEO-спам
            r'<div[^>]*style\s*=\s*["\'][^"\']*position\s*:\s*absolute[^"\']*left\s*:\s*-\d{4,}',
            r'<div[^>]*style\s*=\s*["\'][^"\']*overflow\s*:\s*hidden[^"\']*height\s*:\s*0',
            r'display:none["\'][^>]*>.*?(viagra|cialis|casino|poker|porn|xxx)',
            # Подозрительные внешние скрипты
            r'<script[^>]*src\s*=\s*["\']https?://(?!(?:cdn|ajax|cdnjs|googleapis|gstatic|'
            r'yandex|vk\.com|google|facebook|twitter|cloudflare|jsdelivr|unpkg|bootstrapcdn)\b)',
        ]
        # Подозрительные расширения файлов
        self.suspicious_extensions = [
            '.exe', '.scr', '.bat', '.cmd', '.ps1', '.vbs',
            '.jar', '.msi', '.dll', '.com', '.pif',
            '.hta', '.cpl', '.msp', '.mst', '.ws', '.wsf',
            '.sct', '.reg', '.inf', '.lnk'
        ]
        # Известные вредоносные домены (базовый список — в продакшне нужна полная база)
        self.malicious_domains = [
            'coinhive.com', 'crypto-loot.com', 'coin-imp.com',
            'mineralt.io', 'webmine.pro', 'authedmine.com'
        ]
        # Обязательные заголовки безопасности
        self.required_headers = {
            'Strict-Transport-Security': {
                'description': 'HSTS — принудительное HTTPS',
                'severity': 'high'
            },
            'X-Content-Type-Options': {
                'description': 'Защита от MIME-sniffing',
                'severity': 'medium'
            },
            'X-Frame-Options': {
                'description': 'Защита от clickjacking',
                'severity': 'high'
            },
            'X-XSS-Protection': {
                'description': 'Защита от XSS (устаревший, но полезный)',
                'severity': 'low'
            },
            'Content-Security-Policy': {
                'description': 'Политика безопасности контента',
                'severity': 'high'
            },
            'Referrer-Policy': {
                'description': 'Политика передачи Referer',
                'severity': 'low'
            },
            'Permissions-Policy': {
                'description': 'Политика разрешений (камера, микрофон и т.д.)',
                'severity': 'low'
            }
        }
    async def full_scan(self, domain: str, pages: List[str] = None) -> SecurityScanResult:
        """Полное сканирование безопасности сайта"""
        timestamp = datetime.now()
        result = SecurityScanResult(domain=domain, timestamp=timestamp)
        if pages is None:
            pages = ['/']
        connector = aiohttp.TCPConnector(ssl=False, limit=10)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout
        ) as session:
            # 1. Проверка заголовков безопасности
            await self._check_security_headers(session, domain, result)
            # 2. Сканирование страниц на вредоносный код
            for page_path in pages:
                await self._scan_page_content(session, domain, page_path, result)
            # 3. Проверка через VirusTotal (если есть API ключ)
            if self.vt_api_key:
                await self._check_virustotal(session, domain, result)
            # 4. Проверка наличия WAF
            await self._detect_waf(session, domain, result)
            # 5. Проверка открытых портов и уязвимых сервисов
            await self._check_common_vulnerabilities(session, domain, result)
        # Вычисляем итоговый скор
        result.overall_score = self._calculate_score(result)
        return result
    async def _check_security_headers(
        self, session: aiohttp.ClientSession,
        domain: str, result: SecurityScanResult
    ):
        """Проверка HTTP-заголовков безопасности"""
        try:
            async with session.get(
                f"https://{domain}/", ssl=False, allow_redirects=True
            ) as response:
                headers = response.headers
                for header_name, header_info in self.required_headers.items():
                    present = header_name.lower() in {
                        k.lower() for k in headers.keys()
                    }
                    result.security_headers[header_name] = present
                    if not present:
                        result.threats.append(SecurityThreat(
                            threat_type='missing_header',
                            severity=header_info['severity'],
                            description=(
                                f"Отсутствует заголовок безопасности: "
                                f"{header_name}"
                            ),
                            location=f"https://{domain}/",
                            details=header_info['description'],
                            recommendation=(
                                f"Добавьте заголовок {header_name} "
                                f"в конфигурацию веб-сервера"
                            )
                        ))
                # Проверяем Server header (утечка информации)
                server = headers.get('Server', '')
                if server and any(
                    v in server.lower()
                    for v in ['apache/', 'nginx/', 'iis/', 'php/']
                ):
                    result.threats.append(SecurityThreat(
                        threat_type='info_disclosure',
                        severity='low',
                        description=(
                            f"Заголовок Server раскрывает версию ПО: {server}"
                        ),
                        location=f"https://{domain}/",
                        recommendation=(
                            "Скройте версию веб-сервера в конфигурации"
                        )
                    ))
                # Проверяем X-Powered-By
                powered_by = headers.get('X-Powered-By', '')
                if powered_by:
                    result.threats.append(SecurityThreat(
                        threat_type='info_disclosure',
                        severity='low',
                        description=(
                            f"Заголовок X-Powered-By раскрывает технологию: "
                            f"{powered_by}"
                        ),
                        location=f"https://{domain}/",
                        recommendation="Удалите заголовок X-Powered-By"
                    ))
        except Exception as e:
            logger.error(
                f"Security headers check failed for {domain}: {e}"
            )
    async def _scan_page_content(
        self, session: aiohttp.ClientSession,
        domain: str, page_path: str, result: SecurityScanResult
    ):
        """Сканирование содержимого страницы на вредоносный код"""
        url = f"https://{domain}{page_path}"
        try:
            async with session.get(
                url, ssl=False, allow_redirects=True
            ) as response:
                if response.status != 200:
                    return
                html_content = await response.text()
                # 1. Проверяем паттерны вредоносного кода
                for i, pattern in enumerate(self.malware_patterns):
                    try:
                        matches = re.findall(
                            pattern, html_content, re.IGNORECASE | re.DOTALL
                        )
                        if matches:
                            # Определяем тип угрозы
                            threat_type = self._classify_pattern(pattern)
                            result.malware_detected = True
                            result.threats.append(SecurityThreat(
                                threat_type=threat_type,
                                severity='critical',
                                description=(
                                    f"Обнаружен подозрительный код "
                                    f"(паттерн #{i})"
                                ),
                                location=url,
                                details=(
                                    f"Совпадений: {len(matches)}. "
                                    f"Фрагмент: "
                                    f"{str(matches[0])[:200]}..."
                                ),
                                recommendation=(
                                    "Немедленно проверить и удалить "
                                    "вредоносный код"
                                )
                            ))
                    except re.error:
                        continue
                # 2. Анализ HTML с BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                # Проверяем внешние скрипты
                scripts = soup.find_all('script', src=True)
                for script in scripts:
                    src = script.get('src', '')
                    if src.startswith('http'):
                        parsed = urlparse(src)
                        ext_domain = parsed.netloc
                        result.external_scripts.append(src)
                        # Проверяем на известные вредоносные домены
                        if any(
                            mal_domain in ext_domain
                            for mal_domain in self.malicious_domains
                        ):
                            result.malware_detected = True
                            result.threats.append(SecurityThreat(
                                threat_type='malware_script',
                                severity='critical',
                                description=(
                                    f"Подключён скрипт с известного "
                                    f"вредоносного домена: {ext_domain}"
                                ),
                                location=url,
                                details=f"URL скрипта: {src}",
                                recommendation=(
                                    "Немедленно удалить подключение "
                                    "вредоносного скрипта"
                                )
                            ))
                # Проверяем скрытые iframe
                iframes = soup.find_all('iframe')
                for iframe in iframes:
                    style = iframe.get('style', '')
                    width = iframe.get('width', '')
                    height = iframe.get('height', '')
                    src = iframe.get('src', '')
                    is_hidden = (
                        'display:none' in style.replace(' ', '') or
                        'visibility:hidden' in style.replace(' ', '') or
                        width == '0' or height == '0' or
                        'width:0' in style.replace(' ', '') or
                        'height:0' in style.replace(' ', '')
                    )
                    if is_hidden and src:
                        result.threats.append(SecurityThreat(
                            threat_type='hidden_iframe',
                            severity='critical',
                            description="Обнаружен скрытый iframe",
                            location=url,
                            details=f"iframe src: {src}",
                            recommendation=(
                                "Проверить и удалить скрытый iframe"
                            )
                        ))
                        result.malware_detected = True
                # Проверяем ссылки на подозрительные файлы
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href', '')
                    for ext in self.suspicious_extensions:
                        if href.lower().endswith(ext):
                            result.suspicious_files.append(href)
                            result.threats.append(SecurityThreat(
                                threat_type='suspicious_file',
                                severity='high',
                                description=(
                                    f"Ссылка на подозрительный файл "
                                    f"({ext})"
                                ),
                                location=url,
                                details=f"href: {href}",
                                recommendation=(
                                    "Проверить легитимность файла"
                                )
                            ))
                # 3. Проверяем inline-скрипты
                inline_scripts = soup.find_all('script', src=False)
                for script in inline_scripts:
                    script_content = script.string or ''
                    if len(script_content) < 10:
                        continue
                    # Проверяем на обфускацию
                    obfuscation_indicators = [
                        script_content.count('\\x') > 10,
                        script_content.count('\\u') > 10,
                        script_content.count('String.fromCharCode') > 3,
                        len(re.findall(
                            r'[a-zA-Z_$][a-zA-Z0-9_$]{0,2}\s*=\s*["\'][^"\']{100,}["\']',
                            script_content
                        )) > 3,
                        # Высокая энтропия (много случайных символов)
                        self._calculate_entropy(script_content) > 5.5
                    ]
                    if sum(obfuscation_indicators) >= 2:
                        result.threats.append(SecurityThreat(
                            threat_type='obfuscated_code',
                            severity='high',
                            description=(
                                "Обнаружен обфусцированный JavaScript-код"
                            ),
                            location=url,
                            details=(
                                f"Размер: {len(script_content)} символов. "
                                f"Фрагмент: {script_content[:200]}..."
                            ),
                            recommendation=(
                                "Проверить содержимое обфусцированного скрипта"
                            )
                        ))
        except Exception as e:
            logger.error(
                f"Content scan failed for {url}: {e}"
            )
    def _calculate_entropy(self, text: str) -> float:
        """Вычисление энтропии Шеннона для обнаружения обфускации"""
        import math
        if not text:
            return 0
        freq = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        length = len(text)
        entropy = 0
        for count in freq.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy
    def _classify_pattern(self, pattern: str) -> str:
        """Классификация типа угрозы по паттерну"""
        pattern_lower = pattern.lower()
        if 'eval' in pattern_lower or 'base64' in pattern_lower:
            return 'malware_code'
        elif 'iframe' in pattern_lower:
            return 'hidden_iframe'
        elif 'location' in pattern_lower or 'redirect' in pattern_lower:
            return 'malicious_redirect'
        elif 'coin' in pattern_lower or 'miner' in pattern_lower:
            return 'cryptominer'
        elif any(ext in pattern_lower for ext in ['.exe', '.scr', '.bat']):
            return 'suspicious_download'
        elif 'php' in pattern_lower or 'shell' in pattern_lower:
            return 'webshell'
        elif 'display:none' in pattern_lower:
            return 'seo_spam'
        else:
            return 'suspicious_code'
    async def _check_virustotal(
        self, session: aiohttp.ClientSession,
        domain: str, result: SecurityScanResult
    ):
        """Проверка домена через VirusTotal API"""
        if not self.vt_api_key:
            return
        try:
            headers = {'x-apikey': self.vt_api_key}
            vt_url = (
                f"https://www.virustotal.com/api/v3/domains/{domain}"
            )
            async with session.get(vt_url, headers=headers) as response:
                if response.status != 200:
                    logger.warning(
                        f"VirusTotal API returned {response.status} "
                        f"for {domain}"
                    )
                    return
                data = await response.json()
                attributes = data.get('data', {}).get('attributes', {})
                # Проверяем результаты сканирования
                last_analysis = attributes.get(
                    'last_analysis_stats', {}
                )
                malicious = last_analysis.get('malicious', 0)
                suspicious = last_analysis.get('suspicious', 0)
                if malicious > 0:
                    result.malware_detected = True
                    result.threats.append(SecurityThreat(
                        threat_type='virustotal_detection',
                        severity='critical',
                        description=(
                            f"VirusTotal: {malicious} движков "
                            f"определили сайт как вредоносный"
                        ),
                        location=domain,
                        details=f"Malicious: {malicious}, Suspicious: {suspicious}",
                        recommendation=(
                            "Срочно провести полный аудит безопасности сайта"
                        )
                    ))
                elif suspicious > 0:
                    result.threats.append(SecurityThreat(
                        threat_type='virustotal_suspicious',
                        severity='high',
                        description=(
                            f"VirusTotal: {suspicious} движков "
                            f"отметили сайт как подозрительный"
                        ),
                        location=domain,
                        details=f"Suspicious: {suspicious}",
                        recommendation=(
                            "Провести детальную проверку безопасности"
                        )
                    ))
        except Exception as e:
            logger.error(f"VirusTotal check failed for {domain}: {e}")
    async def _detect_waf(
        self, session: aiohttp.ClientSession,
        domain: str, result: SecurityScanResult
    ):
        """Обнаружение WAF (Web Application Firewall)"""
        waf_signatures = {
            'Cloudflare': ['cf-ray', 'cf-cache-status', '__cfduid'],
            'AWS WAF': ['x-amzn-requestid', 'x-amz-cf-id'],
            'Sucuri': ['x-sucuri-id', 'x-sucuri-cache'],
            'Imperva': ['x-cdn', 'x-iinfo'],
            'Akamai': ['x-akamai-transformed', 'akamai-grn'],
            'ModSecurity': ['mod_security', 'modsecurity'],
            'DDoS-Guard': ['ddos-guard'],
            'Qrator': ['qrator'],
            'StormWall': ['stormwall'],
        }
        try:
            async with session.get(
                f"https://{domain}/", ssl=False, allow_redirects=True
            ) as response:
                headers_lower = {
                    k.lower(): v for k, v in response.headers.items()
                }
                server = headers_lower.get('server', '').lower()
                for waf_name, signatures in waf_signatures.items():
                    for sig in signatures:
                        if (
                            sig.lower() in headers_lower or
                            sig.lower() in server
                        ):
                            result.has_waf = True
                            result.waf_name = waf_name
                            return
            # Пробуем спровоцировать WAF
            test_payloads = [
                "/?id=1' OR '1'='1",
                "/?q=<script>alert(1)</script>",
                "/?file=../../../etc/passwd",
            ]
            for payload in test_payloads:
                try:
                    async with session.get(
                        f"https://{domain}{payload}",
                        ssl=False, allow_redirects=True
                    ) as response:
                        if response.status in (403, 406, 429, 503):
                            result.has_waf = True
                            result.waf_name = "Unknown (detected by behavior)"
                            return
                except Exception:
                    continue
            if not result.has_waf:
                result.threats.append(SecurityThreat(
                    threat_type='no_waf',
                    severity='medium',
                    description="WAF (Web Application Firewall) не обнаружен",
                    location=domain,
                    recommendation=(
                        "Рекомендуется установить WAF "
                        "(Cloudflare, DDoS-Guard или аналог)"
                    )
                ))
        except Exception as e:
            logger.error(f"WAF detection failed for {domain}: {e}")
    async def _check_common_vulnerabilities(
        self, session: aiohttp.ClientSession,
        domain: str, result: SecurityScanResult
    ):
        """Проверка типовых уязвимостей"""
        # 1. Открытые admin-панели
        admin_paths = [
            '/admin/', '/administrator/', '/wp-admin/',
            '/bitrix/admin/', '/modx/manager/', '/admin/login',
            '/panel/', '/cpanel/', '/phpmyadmin/',
            '/adminer.php', '/.env', '/wp-config.php.bak',
            '/config.php.bak', '/database.sql', '/dump.sql',
            '/.git/config', '/.svn/entries',
            '/backup/', '/backups/', '/backup.zip',
            '/backup.tar.gz', '/db.sql'
        ]
        for path in admin_paths:
            try:
                async with session.get(
                    f"https://{domain}{path}",
                    ssl=False, allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        severity = 'critical' if any(
                            p in path for p in [
                                '.env', '.git', '.svn', '.sql',
                                '.bak', 'backup', 'dump'
                            ]
                        ) else 'high'
                        result.threats.append(SecurityThreat(
                            threat_type='exposed_resource',
                            severity=severity,
                            description=(
                                f"Обнаружен доступный ресурс: {path}"
                            ),
                            location=f"https://{domain}{path}",
                            recommendation=(
                                f"Закрыть доступ к {path} через "
                                f"конфигурацию веб-сервера"
                            )
                        ))
            except Exception:
                continue
        # 2. Проверка robots.txt на чувствительные пути
        try:
            async with session.get(
                f"https://{domain}/robots.txt", ssl=False
            ) as response:
                if response.status == 200:
                    robots = await response.text()
                    sensitive_keywords = [
                        'admin', 'backup', 'config', 'database',
                        'private', 'secret', 'password', 'credential'
                    ]
                    for line in robots.split('\n'):
                        line_lower = line.lower()
                        if 'disallow' in line_lower:
                            for keyword in sensitive_keywords:
                                if keyword in line_lower:
                                    result.threats.append(SecurityThreat(
                                        threat_type='info_disclosure',
                                        severity='low',
                                        description=(
                                            f"robots.txt раскрывает "
                                            f"чувствительный путь: "
                                            f"{line.strip()}"
                                        ),
                                        location=(
                                            f"https://{domain}/robots.txt"
                                        ),
                                        recommendation=(
                                            "Убрать чувствительные пути "
                                            "из robots.txt и защитить "
                                            "их иным способом"
                                        )
                                    ))
                                    break
        except Exception:
            pass
    def _calculate_score(self, result: SecurityScanResult) -> int:
        """Расчёт общего скора безопасности"""
        score = 100
        severity_penalties = {
            'critical': 25,
            'high': 15,
            'medium': 8,
            'low': 3,
            'info': 1
        }
        for threat in result.threats:
            penalty = severity_penalties.get(threat.severity, 5)
            score -= penalty
        return max(0, min(100, score))

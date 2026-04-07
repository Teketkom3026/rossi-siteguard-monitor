"""
Модуль проверки доступности сайтов:
- HTTP/HTTPS статус коды
- Время отклика
- DNS резолвинг
- Проверка хостинга (ping, traceroute)
"""
import asyncio
import aiohttp
import dns.resolver
import socket
import time
import subprocess
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
import logging
logger = logging.getLogger(__name__)
@dataclass
class AvailabilityResult:
    domain: str
    timestamp: datetime
    is_available: bool
    http_status: Optional[int] = None
    https_status: Optional[int] = None
    response_time_ms: Optional[float] = None
    dns_resolved: bool = False
    dns_ip: Optional[str] = None
    dns_resolve_time_ms: Optional[float] = None
    ping_ok: bool = False
    ping_time_ms: Optional[float] = None
    ssl_redirect: bool = False
    error_message: Optional[str] = None
    pages_status: Dict[str, dict] = field(default_factory=dict)
class AvailabilityChecker:
    def __init__(self, timeout: int = 30, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self.headers = {
            'User-Agent': 'SiteMonitorBot/1.0 (Internal Monitoring System)'
        }
    async def check_dns(self, domain: str) -> dict:
        """Проверка DNS-резолвинга домена"""
        result = {
            'resolved': False,
            'ip': None,
            'resolve_time_ms': None,
            'error': None
        }
        try:
            start = time.time()
            resolver = dns.resolver.Resolver()
            resolver.timeout = 10
            resolver.lifetime = 10
            answers = resolver.resolve(domain, 'A')
            elapsed = (time.time() - start) * 1000
            result['resolved'] = True
            result['ip'] = str(answers[0])
            result['resolve_time_ms'] = round(elapsed, 2)
            logger.info(f"DNS {domain} -> {result['ip']} ({elapsed:.2f}ms)")
        except dns.resolver.NXDOMAIN:
            result['error'] = f"Домен {domain} не существует (NXDOMAIN)"
            logger.error(result['error'])
        except dns.resolver.NoAnswer:
            result['error'] = f"DNS сервер не вернул ответ для {domain}"
            logger.error(result['error'])
        except dns.resolver.Timeout:
            result['error'] = f"Таймаут DNS запроса для {domain}"
            logger.error(result['error'])
        except Exception as e:
            result['error'] = f"DNS ошибка для {domain}: {str(e)}"
            logger.error(result['error'])
        return result
    async def check_ping(self, domain: str) -> dict:
        """Проверка доступности хоста через ping"""
        result = {
            'ok': False,
            'time_ms': None,
            'error': None
        }
        try:
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '3', '-W', '5', domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=15
            )
            output = stdout.decode()
            if proc.returncode == 0:
                result['ok'] = True
                # Парсинг среднего времени из вывода ping
                for line in output.split('\n'):
                    if 'avg' in line or 'средн' in line:
                        parts = line.split('/')
                        if len(parts) >= 5:
                            result['time_ms'] = float(parts[4])
                            break
            else:
                result['error'] = f"Ping failed: {stderr.decode()}"
        except asyncio.TimeoutError:
            result['error'] = "Ping timeout"
        except Exception as e:
            result['error'] = f"Ping error: {str(e)}"
        return result
    async def check_http(self, domain: str, pages: List[dict] = None) -> dict:
        """Проверка HTTP/HTTPS доступности"""
        result = {
            'http_status': None,
            'https_status': None,
            'response_time_ms': None,
            'ssl_redirect': False,
            'pages': {},
            'error': None
        }
        if pages is None:
            pages = [{'url': '/', 'name': 'Главная'}]
        connector = aiohttp.TCPConnector(
            ssl=False,
            limit=10,
            force_close=True
        )
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        ) as session:
            # Проверяем главную страницу по HTTPS
            for attempt in range(self.retries):
                try:
                    start = time.time()
                    async with session.get(
                        f"https://{domain}/",
                        allow_redirects=True
                    ) as response:
                        elapsed = (time.time() - start) * 1000
                        result['https_status'] = response.status
                        result['response_time_ms'] = round(elapsed, 2)
                        break
                except aiohttp.ClientSSLError:
                    # Пробуем без SSL
                    try:
                        start = time.time()
                        async with session.get(
                            f"http://{domain}/",
                            allow_redirects=True
                        ) as response:
                            elapsed = (time.time() - start) * 1000
                            result['http_status'] = response.status
                            result['response_time_ms'] = round(elapsed, 2)
                            # Проверяем был ли редирект на HTTPS
                            final_url = str(response.url)
                            result['ssl_redirect'] = final_url.startswith('https')
                            break
                    except Exception as e:
                        if attempt == self.retries - 1:
                            result['error'] = str(e)
                except Exception as e:
                    if attempt == self.retries - 1:
                        result['error'] = str(e)
                    await asyncio.sleep(2)
            # Проверяем все страницы из списка
            for page in pages:
                page_url = page['url']
                page_name = page.get('name', page_url)
                page_result = {
                    'status': None,
                    'response_time_ms': None,
                    'error': None,
                    'is_ok': False
                }
                try:
                    start = time.time()
                    url = f"https://{domain}{page_url}"
                    async with session.get(
                        url, allow_redirects=True,
                        ssl=False
                    ) as response:
                        elapsed = (time.time() - start) * 1000
                        page_result['status'] = response.status
                        page_result['response_time_ms'] = round(elapsed, 2)
                        page_result['is_ok'] = 200 <= response.status < 400
                except Exception as e:
                    page_result['error'] = str(e)
                result['pages'][page_name] = page_result
        return result
    async def full_check(
        self, domain: str, pages: List[dict] = None
    ) -> AvailabilityResult:
        """Полная проверка доступности сайта"""
        logger.info(f"Начинаем полную проверку доступности: {domain}")
        timestamp = datetime.now()
        # Параллельно запускаем все проверки
        dns_task = self.check_dns(domain)
        ping_task = self.check_ping(domain)
        http_task = self.check_http(domain, pages)
        dns_result, ping_result, http_result = await asyncio.gather(
            dns_task, ping_task, http_task,
            return_exceptions=True
        )
        # Обрабатываем результаты, если были исключения
        if isinstance(dns_result, Exception):
            dns_result = {
                'resolved': False, 'ip': None,
                'resolve_time_ms': None, 'error': str(dns_result)
            }
        if isinstance(ping_result, Exception):
            ping_result = {
                'ok': False, 'time_ms': None, 'error': str(ping_result)
            }
        if isinstance(http_result, Exception):
            http_result = {
                'http_status': None, 'https_status': None,
                'response_time_ms': None, 'ssl_redirect': False,
                'pages': {}, 'error': str(http_result)
            }
        # Определяем общую доступность
        is_available = (
            dns_result['resolved'] and
            (
                (http_result.get('https_status') and
                 200 <= http_result['https_status'] < 400)
                or
                (http_result.get('http_status') and
                 200 <= http_result['http_status'] < 400)
            )
        )
        # Собираем ошибки
        errors = []
        if dns_result.get('error'):
            errors.append(f"DNS: {dns_result['error']}")
        if ping_result.get('error'):
            errors.append(f"Ping: {ping_result['error']}")
        if http_result.get('error'):
            errors.append(f"HTTP: {http_result['error']}")
        return AvailabilityResult(
            domain=domain,
            timestamp=timestamp,
            is_available=is_available,
            http_status=http_result.get('http_status'),
            https_status=http_result.get('https_status'),
            response_time_ms=http_result.get('response_time_ms'),
            dns_resolved=dns_result['resolved'],
            dns_ip=dns_result.get('ip'),
            dns_resolve_time_ms=dns_result.get('resolve_time_ms'),
            ping_ok=ping_result['ok'],
            ping_time_ms=ping_result.get('time_ms'),
            ssl_redirect=http_result.get('ssl_redirect', False),
            error_message='; '.join(errors) if errors else None,
            pages_status=http_result.get('pages', {})
        )

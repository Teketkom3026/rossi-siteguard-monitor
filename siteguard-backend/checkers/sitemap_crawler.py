"""
Модуль обхода сайта по sitemap.xml:
- Парсинг sitemap.xml
- Проверка каждого URL
- Построение дерева структуры сайта
"""
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
from urllib.parse import urlparse
import logging
logger = logging.getLogger(__name__)
@dataclass
class SitemapPage:
    url: str
    path: str
    name: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    is_ok: bool = False
    parent_path: Optional[str] = None
    children: List[str] = field(default_factory=list)
    last_modified: Optional[str] = None
    priority: Optional[float] = None
    error_message: Optional[str] = None
@dataclass
class SitemapResult:
    domain: str
    timestamp: datetime
    sitemap_found: bool = False
    sitemap_url: Optional[str] = None
    total_pages: int = 0
    pages_ok: int = 0
    pages_error: int = 0
    pages: Dict[str, SitemapPage] = field(default_factory=dict)
    tree_structure: Dict = field(default_factory=dict)
    error_message: Optional[str] = None
class SitemapCrawler:
    def __init__(self, max_concurrent: int = 10, timeout: int = 15):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
    async def crawl(self, domain: str) -> SitemapResult:
        """Полный обход сайта по sitemap"""
        timestamp = datetime.now()
        result = SitemapResult(domain=domain, timestamp=timestamp)
        # 1. Ищем sitemap.xml
        sitemap_urls = [
            f"https://{domain}/sitemap.xml",
            f"https://{domain}/sitemap_index.xml",
            f"https://{domain}/sitemap/sitemap.xml",
            f"http://{domain}/sitemap.xml",
        ]
        urls = []
        connector = aiohttp.TCPConnector(ssl=False, limit=20)
        timeout_cfg = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout_cfg
        ) as session:
            for sitemap_url in sitemap_urls:
                try:
                    async with session.get(sitemap_url) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            result.sitemap_found = True
                            result.sitemap_url = sitemap_url
                            urls = self._parse_sitemap(content, domain)
                            break
                except Exception:
                    continue
            if not result.sitemap_found:
                # Генерируем базовый список страниц для проверки
                result.error_message = (
                    "sitemap.xml не найден, "
                    "используем базовый набор URL"
                )
                urls = self._generate_base_urls(domain)
            result.total_pages = len(urls)
            # 2. Проверяем каждый URL параллельно
            tasks = [
                self._check_url(session, url_info) for url_info in urls
            ]
            pages_results = await asyncio.gather(
                *tasks, return_exceptions=True
            )
            for page_result in pages_results:
                if isinstance(page_result, Exception):
                    continue
                if isinstance(page_result, SitemapPage):
                    result.pages[page_result.path] = page_result
                    if page_result.is_ok:
                        result.pages_ok += 1
                    else:
                        result.pages_error += 1
        # 3. Строим дерево структуры
        result.tree_structure = self._build_tree(result.pages)
        return result
    def _parse_sitemap(self, xml_content: str, domain: str) -> List[dict]:
        """Парсинг sitemap.xml"""
        urls = []
        try:
            root = ET.fromstring(xml_content)
            # Обрабатываем namespace
            ns = {
                'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            # Проверяем тип: sitemap index или обычный sitemap
            if root.tag.endswith('sitemapindex'):
                # Это индексный sitemap — нужно скачать вложенные
                for sitemap in root.findall('.//sm:loc', ns):
                    urls.append({
                        'url': sitemap.text.strip(),
                        'is_sitemap': True
                    })
            else:
                for url_elem in root.findall('.//sm:url', ns):
                    loc = url_elem.find('sm:loc', ns)
                    lastmod = url_elem.find('sm:lastmod', ns)
                    priority = url_elem.find('sm:priority', ns)
                    if loc is not None and loc.text:
                        parsed = urlparse(loc.text.strip())
                        urls.append({
                            'url': loc.text.strip(),
                            'path': parsed.path or '/',
                            'lastmod': (
                                lastmod.text if lastmod is not None
                                else None
                            ),
                            'priority': (
                                float(priority.text)
                                if priority is not None else None
                            ),
                            'is_sitemap': False
                        })
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга sitemap для {domain}: {e}")
        return urls
    def _generate_base_urls(self, domain: str) -> List[dict]:
        """Базовый набор URL если sitemap не найден"""
        base_paths = [
            '/', '/catalog', '/products', '/about',
            '/contacts', '/cart', '/basket',
            '/delivery', '/payment', '/warranty',
            '/news', '/blog', '/faq'
        ]
        return [
            {
                'url': f"https://{domain}{path}",
                'path': path,
                'lastmod': None,
                'priority': None,
                'is_sitemap': False
            }
            for path in base_paths
        ]
    async def _check_url(
        self, session: aiohttp.ClientSession, url_info: dict
    ) -> SitemapPage:
        """Проверка одного URL"""
        import time
        async with self.semaphore:
            url = url_info['url']
            path = url_info.get('path', urlparse(url).path or '/')
            page = SitemapPage(
                url=url,
                path=path,
                name=self._path_to_name(path),
                parent_path=self._get_parent_path(path),
                last_modified=url_info.get('lastmod'),
                priority=url_info.get('priority')
            )
            try:
                start = time.time()
                async with session.get(
                    url, allow_redirects=True, ssl=False
                ) as resp:
                    elapsed = (time.time() - start) * 1000
                    page.status_code = resp.status
                    page.response_time_ms = round(elapsed, 2)
                    page.is_ok = 200 <= resp.status < 400
            except Exception as e:
                page.error_message = str(e)
                page.is_ok = False
            return page
    def _path_to_name(self, path: str) -> str:
        """Преобразование пути в читаемое имя"""
        if path == '/':
            return 'Главная'
        name = path.strip('/').split('/')[-1]
        name = name.replace('-', ' ').replace('_', ' ')
        return name.title()
    def _get_parent_path(self, path: str) -> Optional[str]:
        """Получение родительского пути"""
        if path == '/' or path == '':
            return None
        parts = path.strip('/').split('/')
        if len(parts) <= 1:
            return '/'
        return '/' + '/'.join(parts[:-1])
    def _build_tree(self, pages: Dict[str, SitemapPage]) -> dict:
        """Построение дерева структуры сайта"""
        tree = {
            'name': 'Главная',
            'path': '/',
            'status': 'ok' if '/' in pages and pages['/'].is_ok else 'error',
            'children': []
        }
        # Группируем страницы по уровням
        for path, page in sorted(pages.items()):
            if path == '/':
                continue
            parts = path.strip('/').split('/')
            current = tree
            for i, part in enumerate(parts):
                current_path = '/' + '/'.join(parts[:i + 1])
                found = False
                for child in current['children']:
                    if child['path'] == current_path:
                        current = child
                        found = True
                        break
                if not found:
                    page_data = pages.get(current_path)
                    new_node = {
                        'name': (
                            page_data.name if page_data
                            else self._path_to_name(current_path)
                        ),
                        'path': current_path,
                        'status': (
                            'ok' if page_data and page_data.is_ok
                            else 'error' if page_data
                            else 'unknown'
                        ),
                        'status_code': (
                            page_data.status_code if page_data else None
                        ),
                        'response_time_ms': (
                            page_data.response_time_ms if page_data else None
                        ),
                        'children': []
                    }
                    current['children'].append(new_node)
                    current = new_node
        return tree

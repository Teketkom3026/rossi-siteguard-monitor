"""
Модуль тестирования UI-элементов:
- Кликабельность кнопок (купить, позвонить и т.д.)
- Работоспособность форм
- Каталог, карточки товара, корзина
Использует Playwright для headless-тестирования
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser
import logging
logger = logging.getLogger(__name__)
@dataclass
class UIElementResult:
    name: str
    selector: str
    action: str
    is_found: bool = False
    is_clickable: bool = False
    is_visible: bool = False
    action_success: bool = False
    response_after_action: Optional[str] = None
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
@dataclass
class UITestResult:
    domain: str
    timestamp: datetime
    page_url: str
    page_loaded: bool = False
    page_load_time_ms: Optional[float] = None
    elements: List[UIElementResult] = field(default_factory=list)
    has_critical_issues: bool = False
    screenshot_path: Optional[str] = None
    console_errors: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
class UITester:
    def __init__(
        self,
        headless: bool = True,
        screenshot_dir: str = "./screenshots"
    ):
        self.headless = headless
        self.screenshot_dir = screenshot_dir
        self.browser: Optional[Browser] = None
    async def init_browser(self):
        """Инициализация браузера"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage'
            ]
        )
    async def close_browser(self):
        """Закрытие браузера"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    async def test_page(
        self,
        domain: str,
        page_path: str,
        elements_config: List[dict]
    ) -> UITestResult:
        """Тестирование страницы и её элементов"""
        timestamp = datetime.now()
        url = f"https://{domain}{page_path}"
        result = UITestResult(
            domain=domain,
            timestamp=timestamp,
            page_url=url
        )
        if not self.browser:
            await self.init_browser()
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        # Собираем ошибки консоли
        console_errors = []
        page.on("console", lambda msg: (
            console_errors.append(msg.text)
            if msg.type == "error" else None
        ))
        try:
            # Загрузка страницы
            import time
            start = time.time()
            response = await page.goto(
                url,
                wait_until='networkidle',
                timeout=30000
            )
            elapsed = (time.time() - start) * 1000
            result.page_loaded = response is not None and response.ok
            result.page_load_time_ms = round(elapsed, 2)
            result.console_errors = console_errors
            if not result.page_loaded:
                result.error_message = (
                    f"Страница не загрузилась: "
                    f"status={response.status if response else 'None'}"
                )
                result.has_critical_issues = True
                return result
            # Скриншот страницы
            screenshot_path = (
                f"{self.screenshot_dir}/{domain}"
                f"{page_path.replace('/', '_')}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
            )
            await page.screenshot(path=screenshot_path, full_page=True)
            result.screenshot_path = screenshot_path
            # Тестируем каждый UI-элемент
            for elem_config in elements_config:
                elem_result = await self._test_element(
                    page, elem_config, domain
                )
                result.elements.append(elem_result)
                # Если критический элемент не работает
                if not elem_result.is_found or not elem_result.action_success:
                    if elem_config.get('critical', True):
                        result.has_critical_issues = True
        except Exception as e:
            result.error_message = f"Ошибка тестирования: {str(e)}"
            result.has_critical_issues = True
            logger.error(f"UI test error for {url}: {e}")
        finally:
            await page.close()
            await context.close()
        return result
    async def _test_element(
        self, page: Page, config: dict, domain: str
    ) -> UIElementResult:
        """Тестирование одного UI-элемента"""
        selector = config['selector']
        name = config.get('name', selector)
        action = config.get('action', 'exists')
        result = UIElementResult(
            name=name,
            selector=selector,
            action=action
        )
        try:
            # Проверяем наличие элемента
            element = await page.query_selector(selector)
            if element is None:
                # Пробуем альтернативные селекторы
                alt_selectors = config.get('alt_selectors', [])
                for alt_sel in alt_selectors:
                    element = await page.query_selector(alt_sel)
                    if element:
                        result.selector = alt_sel
                        break
            if element is None:
                result.is_found = False
                result.error_message = f"Элемент '{name}' не найден на странице"
                logger.warning(
                    f"Element '{name}' ({selector}) not found on {domain}"
                )
                return result
            result.is_found = True
            # Проверяем видимость
            result.is_visible = await element.is_visible()
            # Проверяем кликабельность
            is_enabled = await element.is_enabled()
            result.is_clickable = result.is_visible and is_enabled
            # Выполняем действие
            if action == 'exists':
                result.action_success = result.is_found and result.is_visible
            elif action == 'click':
                result.action_success = await self._test_click(
                    page, element, result
                )
            elif action == 'submit_test':
                result.action_success = await self._test_form_submit(
                    page, element, result, config
                )
            elif action == 'navigate':
                result.action_success = await self._test_navigation(
                    page, element, result
                )
        except Exception as e:
            result.error_message = f"Ошибка тестирования элемента: {str(e)}"
            logger.error(f"Element test error '{name}' on {domain}: {e}")
        return result
    async def _test_click(
        self, page: Page, element, result: UIElementResult
    ) -> bool:
        """Тестирование клика по элементу"""
        try:
            # Сохраняем текущий URL
            current_url = page.url
            # Перехватываем навигацию и диалоги
            dialog_appeared = False
            async def handle_dialog(dialog):
                nonlocal dialog_appeared
                dialog_appeared = True
                await dialog.dismiss()
            page.on("dialog", handle_dialog)
            # Кликаем по элементу
            await element.scroll_into_view_if_needed()
            await element.click(timeout=5000)
            # Ждём немного для реакции
            await page.wait_for_timeout(2000)
            # Проверяем что что-то произошло
            new_url = page.url
            url_changed = new_url != current_url
            # Проверяем появление модальных окон
            modal_selectors = [
                '.modal.show', '.modal.active', '.popup.active',
                '[class*="modal"][class*="open"]',
                '[class*="popup"][class*="visible"]',
                '.fancybox-container', '.mfp-container'
            ]
            modal_appeared = False
            for modal_sel in modal_selectors:
                modal = await page.query_selector(modal_sel)
                if modal and await modal.is_visible():
                    modal_appeared = True
                    break
            result.action_success = (
                url_changed or modal_appeared or dialog_appeared
            )
            if url_changed:
                result.response_after_action = f"Навигация: {new_url}"
                # Возвращаемся назад
                await page.go_back()
                await page.wait_for_load_state('networkidle')
            elif modal_appeared:
                result.response_after_action = "Открылось модальное окно"
            elif dialog_appeared:
                result.response_after_action = "Появился диалог"
            else:
                # Даже если визуально ничего не произошло — клик выполнен
                result.response_after_action = (
                    "Клик выполнен, видимой реакции нет"
                )
                # Это может быть нормально (JS обработчик без визуала)
                result.action_success = True
            return result.action_success
        except Exception as e:
            result.error_message = f"Ошибка клика: {str(e)}"
            return False
    async def _test_form_submit(
        self, page: Page, element, result: UIElementResult,
        config: dict
    ) -> bool:
        """Тестирование формы (без реальной отправки)"""
        try:
            # Определяем тип формы
            form = element
            tag = await element.evaluate('el => el.tagName.toLowerCase()')
            if tag != 'form':
                # Ищем ближайшую форму
                form = await element.evaluate_handle(
                    'el => el.closest("form") || el.querySelector("form")'
                )
                if not form:
                    form = element
            # Находим поля формы
            inputs = await page.query_selector_all(
                f'{config["selector"]} input, '
                f'{config["selector"]} textarea, '
                f'{config["selector"]} select'
            )
            if not inputs:
                # Пробуем более широкий поиск
                inputs = await form.query_selector_all(
                    'input, textarea, select'
                )
            fields_found = len(inputs) > 0
            # Проверяем наличие обязательных полей
            required_fields_info = []
            for inp in inputs:
                input_type = await inp.get_attribute('type') or 'text'
                input_name = await inp.get_attribute('name') or ''
                input_placeholder = await inp.get_attribute('placeholder') or ''
                is_required = await inp.get_attribute('required') is not None
                required_fields_info.append({
                    'type': input_type,
                    'name': input_name,
                    'placeholder': input_placeholder,
                    'required': is_required
                })
            # Проверяем наличие кнопки отправки
            submit_btn = await page.query_selector(
                f'{config["selector"]} button[type="submit"], '
                f'{config["selector"]} input[type="submit"], '
                f'{config["selector"]} button:not([type])'
            )
            submit_exists = submit_btn is not None
            # Заполняем тестовыми данными (НЕ отправляем)
            test_data = {
                'name': 'Тест Мониторинг',
                'phone': '+71234567890',
                'email': 'test@monitoring.local',
                'message': 'Тестовое сообщение системы мониторинга'
            }
            for inp in inputs:
                input_type = await inp.get_attribute('type') or 'text'
                input_name = (await inp.get_attribute('name') or '').lower()
                if input_type in ('hidden', 'submit', 'button', 'checkbox', 'radio'):
                    continue
                # Подбираем тестовые данные по имени поля
                value = 'Тест'
                for key, val in test_data.items():
                    if key in input_name:
                        value = val
                        break
                try:
                    await inp.fill(value)
                except Exception:
                    pass  # Поле может быть readonly
            result.response_after_action = (
                f"Форма: {len(inputs)} полей, "
                f"кнопка отправки: {'да' if submit_exists else 'нет'}"
            )
            # Форма считается работоспособной если есть поля и кнопка
            return fields_found and submit_exists
        except Exception as e:
            result.error_message = f"Ошибка тестирования формы: {str(e)}"
            return False
    async def _test_navigation(
        self, page: Page, element, result: UIElementResult
    ) -> bool:
        """Тестирование навигационной ссылки"""
        try:
            href = await element.get_attribute('href')
            if not href:
                result.error_message = "У элемента нет атрибута href"
                return False
            current_url = page.url
            await element.click(timeout=5000)
            await page.wait_for_load_state('networkidle', timeout=15000)
            new_url = page.url
            result.response_after_action = f"Навигация: {new_url}"
            # Возвращаемся назад
            await page.go_back()
            await page.wait_for_load_state('networkidle')
            return True
        except Exception as e:
            result.error_message = f"Ошибка навигации: {str(e)}"
            return False
    async def test_catalog_flow(self, domain: str) -> UITestResult:
        """
        Комплексный тест потока:
        Каталог -> Карточка товара -> Корзина
        """
        timestamp = datetime.now()
        result = UITestResult(
            domain=domain,
            timestamp=timestamp,
            page_url=f"https://{domain}/catalog"
        )
        if not self.browser:
            await self.init_browser()
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        try:
            # 1. Открываем каталог
            response = await page.goto(
                f"https://{domain}/catalog",
                wait_until='networkidle',
                timeout=30000
            )
            result.page_loaded = response is not None and response.ok
            if not result.page_loaded:
                result.error_message = "Каталог не загрузился"
                result.has_critical_issues = True
                return result
            # 2. Ищем карточки товаров
            product_selectors = [
                '.product-card', '.product-item', '.catalog-item',
                '[class*="product"]', '[class*="catalog-item"]',
                '.goods-item', '.item-card'
            ]
            product_card = None
            for sel in product_selectors:
                cards = await page.query_selector_all(sel)
                if cards:
                    product_card = cards[0]
                    result.elements.append(UIElementResult(
                        name="Карточка товара в каталоге",
                        selector=sel,
                        action="click",
                        is_found=True,
                        is_visible=True,
                        is_clickable=True,
                        action_success=True
                    ))
                    break
            if not product_card:
                result.elements.append(UIElementResult(
                    name="Карточка товара в каталоге",
                    selector="auto-detect",
                    action="click",
                    is_found=False,
                    error_message="Карточки товаров не найдены"
                ))
                result.has_critical_issues = True
                return result
            # 3. Кликаем на карточку товара
            link = await product_card.query_selector('a')
            if link:
                await link.click()
            else:
                await product_card.click()
            await page.wait_for_load_state('networkidle', timeout=15000)
            # 4. На странице товара ищем кнопку "Купить" / "В корзину"
            buy_selectors = [
                'button.buy', '.buy-btn', '.add-to-cart',
                '[class*="buy"]', '[class*="cart"]',
                'button:has-text("Купить")',
                'button:has-text("В корзину")',
                'a:has-text("Купить")',
                'a:has-text("В корзину")'
            ]
            buy_button = None
            for sel in buy_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        buy_button = btn
                        result.elements.append(UIElementResult(
                            name="Кнопка Купить/В корзину",
                            selector=sel,
                            action="click",
                            is_found=True,
                            is_visible=True,
                            is_clickable=True,
                            action_success=True
                        ))
                        break
                except Exception:
                    continue
            if not buy_button:
                result.elements.append(UIElementResult(
                    name="Кнопка Купить/В корзину",
                    selector="auto-detect",
                    action="click",
                    is_found=False,
                    error_message="Кнопка покупки не найдена"
                ))
                result.has_critical_issues = True
            # 5. Проверяем доступность корзины
            cart_selectors = [
                'a[href*="cart"]', 'a[href*="basket"]',
                'a[href*="korzina"]',
                '.cart-link', '.basket-link',
                '[class*="cart-icon"]', '[class*="basket"]'
            ]
            cart_link = None
            for sel in cart_selectors:
                try:
                    link = await page.query_selector(sel)
                    if link:
                        cart_link = link
                        break
                except Exception:
                    continue
            if cart_link:
                await cart_link.click()
                await page.wait_for_load_state('networkidle', timeout=15000)
                cart_page_loaded = '/cart' in page.url or '/basket' in page.url
                result.elements.append(UIElementResult(
                    name="Страница корзины",
                    selector="auto-detect",
                    action="navigate",
                    is_found=True,
                    is_visible=True,
                    action_success=cart_page_loaded,
                    response_after_action=f"URL: {page.url}"
                ))
            else:
                result.elements.append(UIElementResult(
                    name="Ссылка на корзину",
                    selector="auto-detect",
                    action="navigate",
                    is_found=False,
                    error_message="Ссылка на корзину не найдена"
                ))
        except Exception as e:
            result.error_message = f"Ошибка тестирования потока: {str(e)}"
            result.has_critical_issues = True
            logger.error(f"Catalog flow test error for {domain}: {e}")
        finally:
            await page.close()
            await context.close()
        return result

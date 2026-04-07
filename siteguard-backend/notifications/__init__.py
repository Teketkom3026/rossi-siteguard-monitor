"""
Единый менеджер уведомлений — маршрутизация по каналам и severity
"""
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import logging

from .telegram_bot import TelegramNotifier
from .email_sender import EmailNotifier
from .sms_sender import SMSNotifier

logger = logging.getLogger(__name__)


class NotificationManager:
    def __init__(self, config: dict):
        self.config = config

        # Инициализация каналов
        self.telegram = None
        self.email = None
        self.sms = None

        if config.get('telegram', {}).get('enabled'):
            tg_cfg = config['telegram']
            self.telegram = TelegramNotifier(
                bot_token=tg_cfg['bot_token'],
                chat_ids=tg_cfg['chat_ids']
            )

        if config.get('email', {}).get('enabled'):
            em_cfg = config['email']
            self.email = EmailNotifier(
                smtp_host=em_cfg['smtp_host'],
                smtp_port=em_cfg['smtp_port'],
                smtp_user=em_cfg['smtp_user'],
                smtp_password=em_cfg['smtp_password'],
                from_email=em_cfg['from_email'],
                to_emails=em_cfg['to_emails']
            )

        if config.get('sms', {}).get('enabled'):
            sms_cfg = config['sms']
            self.sms = SMSNotifier(
                provider=sms_cfg['provider'],
                api_key=sms_cfg['api_key'],
                phone_numbers=sms_cfg['phone_numbers'],
                smsc_login=sms_cfg.get('smsc_login'),
                smsc_password=sms_cfg.get('smsc_password')
            )

        # Кэш последних уведомлений (антифлуд)
        self._sent_cache: Dict[str, datetime] = {}
        self._cooldown_minutes = config.get('cooldown_minutes', 15)

    def _should_send(self, cache_key: str) -> bool:
        """Проверка антифлуда — не слать дубли слишком часто"""
        now = datetime.now()
        if cache_key in self._sent_cache:
            last_sent = self._sent_cache[cache_key]
            if now - last_sent < timedelta(
                minutes=self._cooldown_minutes
            ):
                return False
        self._sent_cache[cache_key] = now
        return True

    async def send_alert(
        self,
        domain: str,
        alert_type: str,
        severity: str,
        description: str,
        details: Optional[str] = None,
        recommendation: Optional[str] = None
    ):
        """Отправка уведомления по всем каналам"""
        # Антифлуд
        cache_key = f"{domain}:{alert_type}:{severity}"
        if not self._should_send(cache_key):
            logger.debug(
                f"Alert suppressed (cooldown): {cache_key}"
            )
            return

        tasks = []

        # Telegram — все severity
        if self.telegram:
            tasks.append(self.telegram.send_alert(
                domain, alert_type, severity,
                description, details, recommendation
            ))

        # Email — medium и выше
        if self.email and severity in (
            'critical', 'high', 'medium'
        ):
            tasks.append(self.email.send_alert(
                domain, alert_type, severity,
                description, details, recommendation
            ))

        # SMS — только critical и high
        if self.sms and severity in ('critical', 'high'):
            tasks.append(self.sms.send_alert(
                domain, severity, description
            ))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_recovery(self, domain: str, description: str):
        """Уведомление о восстановлении"""
        tasks = []
        if self.telegram:
            tasks.append(
                self.telegram.send_recovery(domain, description)
            )
        if self.email:
            tasks.append(self.email.send_alert(
                domain, 'Восстановление', 'info',
                description
            ))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_daily_report(self, report_data: dict):
        """Ежедневный отчёт"""
        tasks = []
        if self.telegram:
            tasks.append(
                self.telegram.send_daily_report(report_data)
            )
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self):
        """Закрытие всех подключений"""
        if self.telegram:
            await self.telegram.close()

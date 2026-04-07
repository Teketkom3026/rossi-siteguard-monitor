"""
SMS-уведомления (через SMS.RU / SMS Aero / SMSC.ru API)
"""
import aiohttp
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SMSNotifier:
    """Поддержка нескольких SMS-провайдеров"""

    def __init__(
        self,
        provider: str = 'smsru',
        api_key: str = '',
        phone_numbers: List[str] = None,
        # Для SMSC
        smsc_login: Optional[str] = None,
        smsc_password: Optional[str] = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.phone_numbers = phone_numbers or []
        self.smsc_login = smsc_login
        self.smsc_password = smsc_password

    async def send_alert(
        self,
        domain: str,
        severity: str,
        description: str
    ):
        """Отправка SMS (только для critical и high)"""
        if severity not in ('critical', 'high'):
            return  # SMS только для критических проблем

        timestamp = datetime.now().strftime('%H:%M')
        message = (
            f"[{severity.upper()}] {domain}: {description} ({timestamp})"
        )

        # Ограничение длины SMS
        if len(message) > 160:
            message = message[:157] + "..."

        for phone in self.phone_numbers:
            try:
                if self.provider == 'smsru':
                    await self._send_smsru(phone, message)
                elif self.provider == 'smsc':
                    await self._send_smsc(phone, message)
                elif self.provider == 'smsaero':
                    await self._send_smsaero(phone, message)
                logger.info(f"SMS sent to {phone}: {message}")
            except Exception as e:
                logger.error(f"SMS send error to {phone}: {e}")

    async def _send_smsru(self, phone: str, message: str):
        """Отправка через SMS.RU"""
        async with aiohttp.ClientSession() as session:
            params = {
                'api_id': self.api_key,
                'to': phone,
                'msg': message,
                'json': 1
            }
            async with session.get(
                'https://sms.ru/sms/send',
                params=params
            ) as response:
                result = await response.json()
                if result.get('status') != 'OK':
                    raise Exception(
                        f"SMS.RU error: {result.get('status_text')}"
                    )

    async def _send_smsc(self, phone: str, message: str):
        """Отправка через SMSC.ru"""
        async with aiohttp.ClientSession() as session:
            params = {
                'login': self.smsc_login,
                'psw': self.smsc_password,
                'phones': phone,
                'mes': message,
                'fmt': 3  # JSON
            }
            async with session.get(
                'https://smsc.ru/sys/send.php',
                params=params
            ) as response:
                result = await response.json()
                if 'error' in result:
                    raise Exception(
                        f"SMSC error: {result.get('error')}"
                    )

    async def _send_smsaero(self, phone: str, message: str):
        """Отправка через SMS Aero"""
        async with aiohttp.ClientSession() as session:
            url = (
                f"https://gate.smsaero.ru/v2/sms/send"
            )
            params = {
                'number': phone,
                'text': message,
                'sign': 'SMS Aero'
            }
            auth = aiohttp.BasicAuth(
                login=self.smsc_login or '',
                password=self.api_key
            )
            async with session.get(
                url, params=params, auth=auth
            ) as response:
                result = await response.json()
                if not result.get('success'):
                    raise Exception(
                        f"SMS Aero error: {result.get('message')}"
                    )

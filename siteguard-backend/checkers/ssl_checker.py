"""
Модуль проверки SSL-сертификатов:
- Наличие сертификата
- Срок действия
- Валидность цепочки
- Соответствие домену
"""
import ssl
import socket
import asyncio
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, List
from cryptography import x509
from cryptography.x509.oid import NameOID
import logging
logger = logging.getLogger(__name__)
@dataclass
class SSLCheckResult:
    domain: str
    timestamp: datetime
    has_ssl: bool
    is_valid: bool = False
    issuer: Optional[str] = None
    subject: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    days_until_expiry: Optional[int] = None
    is_expiring_soon: bool = False       # < 30 дней
    is_expired: bool = False
    protocol_version: Optional[str] = None
    cipher_suite: Optional[str] = None
    san_domains: List[str] = None
    chain_valid: bool = False
    error_message: Optional[str] = None
    def __post_init__(self):
        if self.san_domains is None:
            self.san_domains = []
class SSLChecker:
    def __init__(self, warning_days: int = 30, critical_days: int = 7):
        self.warning_days = warning_days
        self.critical_days = critical_days
    async def check_ssl(self, domain: str, port: int = 443) -> SSLCheckResult:
        """Полная проверка SSL-сертификата"""
        timestamp = datetime.now()
        result = SSLCheckResult(
            domain=domain,
            timestamp=timestamp,
            has_ssl=False
        )
        try:
            # Создаём SSL контекст
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            # Подключаемся к серверу
            loop = asyncio.get_event_loop()
            cert_info = await loop.run_in_executor(
                None,
                self._get_cert_info,
                domain, port, context
            )
            if cert_info is None:
                result.error_message = "Не удалось получить сертификат"
                return result
            result.has_ssl = True
            cert = cert_info['cert']
            cert_binary = cert_info['cert_binary']
            # Парсим информацию о сертификате
            # Издатель
            issuer_parts = []
            for item in cert.get('issuer', []):
                for key, value in item:
                    if key == 'organizationName':
                        issuer_parts.append(value)
            result.issuer = ', '.join(issuer_parts) if issuer_parts else 'Unknown'
            # Субъект
            subject_parts = []
            for item in cert.get('subject', []):
                for key, value in item:
                    if key == 'commonName':
                        subject_parts.append(value)
            result.subject = ', '.join(subject_parts) if subject_parts else 'Unknown'
            # Даты действия
            not_before = cert.get('notBefore')
            not_after = cert.get('notAfter')
            if not_before:
                result.valid_from = datetime.strptime(
                    not_before, '%b %d %H:%M:%S %Y %Z'
                )
            if not_after:
                result.valid_until = datetime.strptime(
                    not_after, '%b %d %H:%M:%S %Y %Z'
                )
                delta = result.valid_until - datetime.utcnow()
                result.days_until_expiry = delta.days
                result.is_expired = delta.days < 0
                result.is_expiring_soon = (
                    0 <= delta.days <= self.warning_days
                )
            # SAN домены
            san = cert.get('subjectAltName', [])
            result.san_domains = [
                value for typ, value in san if typ == 'DNS'
            ]
            # Протокол и шифрование
            result.protocol_version = cert_info.get('protocol')
            result.cipher_suite = cert_info.get('cipher')
            # Проверка валидности
            result.is_valid = (
                not result.is_expired and
                result.has_ssl
            )
            result.chain_valid = cert_info.get('chain_valid', False)
            logger.info(
                f"SSL {domain}: valid={result.is_valid}, "
                f"expires={result.days_until_expiry} days, "
                f"issuer={result.issuer}"
            )
        except ssl.SSLCertVerificationError as e:
            result.error_message = f"Ошибка верификации SSL: {str(e)}"
            result.is_valid = False
            logger.error(f"SSL verification error for {domain}: {e}")
        except ssl.SSLError as e:
            result.error_message = f"SSL ошибка: {str(e)}"
            logger.error(f"SSL error for {domain}: {e}")
        except socket.timeout:
            result.error_message = "Таймаут подключения"
            logger.error(f"SSL timeout for {domain}")
        except ConnectionRefusedError:
            result.error_message = "Соединение отклонено (порт 443 закрыт)"
            logger.error(f"SSL connection refused for {domain}")
        except Exception as e:
            result.error_message = f"Неизвестная ошибка: {str(e)}"
            logger.error(f"SSL unknown error for {domain}: {e}")
        return result
    def _get_cert_info(
        self, domain: str, port: int, context: ssl.SSLContext
    ) -> Optional[dict]:
        """Синхронное получение информации о сертификате"""
        try:
            with socket.create_connection(
                (domain, port), timeout=10
            ) as sock:
                with context.wrap_socket(
                    sock, server_hostname=domain
                ) as ssock:
                    cert = ssock.getpeercert()
                    cert_binary = ssock.getpeercert(binary_form=True)
                    protocol = ssock.version()
                    cipher = ssock.cipher()
                    return {
                        'cert': cert,
                        'cert_binary': cert_binary,
                        'protocol': protocol,
                        'cipher': cipher[0] if cipher else None,
                        'chain_valid': True  # Если мы дошли сюда — цепочка валидна
                    }
        except ssl.SSLCertVerificationError:
            # Пробуем без верификации чтобы получить информацию
            ctx_no_verify = ssl.create_default_context()
            ctx_no_verify.check_hostname = False
            ctx_no_verify.verify_mode = ssl.CERT_NONE
            try:
                with socket.create_connection(
                    (domain, port), timeout=10
                ) as sock:
                    with ctx_no_verify.wrap_socket(
                        sock, server_hostname=domain
                    ) as ssock:
                        cert = ssock.getpeercert()
                        cert_binary = ssock.getpeercert(binary_form=True)
                        return {
                            'cert': cert,
                            'cert_binary': cert_binary,
                            'protocol': ssock.version(),
                            'cipher': ssock.cipher()[0] if ssock.cipher() else None,
                            'chain_valid': False
                        }
            except Exception:
                return None
        except Exception:
            return None

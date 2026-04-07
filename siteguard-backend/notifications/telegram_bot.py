"""
Telegram-бот для уведомлений о проблемах
"""
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_ids: List[str]):
        self.bot = Bot(token=bot_token)
        self.chat_ids = chat_ids

    async def send_alert(
        self,
        domain: str,
        alert_type: str,
        severity: str,
        description: str,
        details: Optional[str] = None,
        recommendation: Optional[str] = None
    ):
        """Отправка уведомления о проблеме"""
        severity_emoji = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🔵',
            'info': 'ℹ️'
        }
        emoji = severity_emoji.get(severity, '⚪')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        message = (
            f"{emoji} <b>АЛЕРТ [{severity.upper()}]</b>\n\n"
            f"🌐 <b>Сайт:</b> {domain}\n"
            f"📋 <b>Тип:</b> {alert_type}\n"
            f"📝 <b>Описание:</b> {description}\n"
            f"🕐 <b>Время:</b> {timestamp}\n"
        )

        if details:
            message += f"\n📎 <b>Детали:</b>\n<code>{details[:500]}</code>\n"

        if recommendation:
            message += f"\n💡 <b>Рекомендация:</b> {recommendation}\n"

        message += f"\n🔗 https://{domain}"

        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(
                    f"Telegram send error to {chat_id}: {e}"
                )

    async def send_recovery(self, domain: str, description: str):
        """Уведомление о восстановлении"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = (
            f"✅ <b>ВОССТАНОВЛЕНО</b>\n\n"
            f"🌐 <b>Сайт:</b> {domain}\n"
            f"📝 <b>Описание:</b> {description}\n"
            f"🕐 <b>Время:</b> {timestamp}\n"
            f"\n🔗 https://{domain}"
        )

        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(
                    f"Telegram recovery send error to {chat_id}: {e}"
                )

    async def send_daily_report(self, report_data: dict):
        """Ежедневный отчёт"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        total_sites = report_data.get('total_sites', 0)
        sites_ok = report_data.get('sites_ok', 0)
        sites_with_issues = report_data.get('sites_with_issues', 0)
        critical_issues = report_data.get('critical_issues', 0)

        message = (
            f"📊 <b>ЕЖЕДНЕВНЫЙ ОТЧЁТ</b>\n"
            f"🕐 {timestamp}\n\n"
            f"📈 <b>Всего сайтов:</b> {total_sites}\n"
            f"✅ <b>Работают нормально:</b> {sites_ok}\n"
            f"⚠️ <b>Есть проблемы:</b> {sites_with_issues}\n"
            f"🔴 <b>Критических проблем:</b> {critical_issues}\n"
        )

        # Добавляем статус каждого сайта
        sites_status = report_data.get('sites_status', {})
        if sites_status:
            message += "\n<b>Статус сайтов:</b>\n"
            for domain, status in sites_status.items():
                if status['is_ok']:
                    message += f"  ✅ {domain}\n"
                else:
                    issues_count = status.get('issues_count', 0)
                    message += (
                        f"  🔴 {domain} "
                        f"({issues_count} проблем)\n"
                    )

        # SSL-сертификаты, истекающие скоро
        expiring_ssl = report_data.get('expiring_ssl', [])
        if expiring_ssl:
            message += "\n⏰ <b>SSL истекает скоро:</b>\n"
            for ssl_info in expiring_ssl:
                message += (
                    f"  ⚠️ {ssl_info['domain']}: "
                    f"{ssl_info['days_left']} дней\n"
                )

        # Безопасность
        security_issues = report_data.get('security_summary', {})
        if security_issues:
            message += "\n🛡️ <b>Безопасность:</b>\n"
            for domain, score in security_issues.items():
                if score < 50:
                    emoji = "🔴"
                elif score < 75:
                    emoji = "🟡"
                else:
                    emoji = "✅"
                message += f"  {emoji} {domain}: {score}/100\n"

        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(
                    f"Telegram daily report error to {chat_id}: {e}"
                )

    async def close(self):
        """Закрытие сессии бота"""
        await self.bot.session.close()

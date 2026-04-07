"""
Email-уведомления о проблемах
"""
import asyncio
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class EmailNotifier:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
        to_emails: List[str],
        use_tls: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_emails = to_emails
        self.use_tls = use_tls

    async def send_alert(
        self,
        domain: str,
        alert_type: str,
        severity: str,
        description: str,
        details: Optional[str] = None,
        recommendation: Optional[str] = None
    ):
        """Отправка email-уведомления"""
        severity_colors = {
            'critical': '#FF0000',
            'high': '#FF6600',
            'medium': '#FFCC00',
            'low': '#0066FF',
            'info': '#999999'
        }
        color = severity_colors.get(severity, '#999999')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        subject = (
            f"[{severity.upper()}] Проблема с сайтом {domain} — {alert_type}"
        )

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .alert-header {{
                    background-color: {color};
                    color: white;
                    padding: 15px 20px;
                    border-radius: 8px 8px 0 0;
                    font-size: 18px;
                    font-weight: bold;
                }}
                .alert-body {{
                    background-color: #f9f9f9;
                    padding: 20px;
                    border: 1px solid #ddd;
                    border-top: none;
                    border-radius: 0 0 8px 8px;
                }}
                .field {{ margin-bottom: 12px; }}
                .field-label {{
                    font-weight: bold;
                    color: #333;
                    display: inline-block;
                    width: 150px;
                }}
                .field-value {{ color: #555; }}
                .details-block {{
                    background-color: #fff;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 12px;
                    margin-top: 10px;
                    font-family: monospace;
                    font-size: 13px;
                    white-space: pre-wrap;
                }}
                .recommendation {{
                    background-color: #e8f5e9;
                    border-left: 4px solid #4caf50;
                    padding: 12px;
                    margin-top: 15px;
                    border-radius: 0 4px 4px 0;
                }}
                .footer {{
                    margin-top: 20px;
                    color: #999;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="alert-header">
                ⚠️ АЛЕРТ [{severity.upper()}] — {domain}
            </div>
            <div class="alert-body">
                <div class="field">
                    <span class="field-label">🌐 Сайт:</span>
                    <span class="field-value">
                        <a href="https://{domain}">{domain}</a>
                    </span>
                </div>
                <div class="field">
                    <span class="field-label">📋 Тип проблемы:</span>
                    <span class="field-value">{alert_type}</span>
                </div>
                <div class="field">
                    <span class="field-label">📝 Описание:</span>
                    <span class="field-value">{description}</span>
                </div>
                <div class="field">
                    <span class="field-label">🕐 Время:</span>
                    <span class="field-value">{timestamp}</span>
                </div>
        """

        if details:
            html_body += f"""
                <div class="field">
                    <span class="field-label">📎 Детали:</span>
                    <div class="details-block">{details}</div>
                </div>
            """

        if recommendation:
            html_body += f"""
                <div class="recommendation">
                    💡 <b>Рекомендация:</b> {recommendation}
                </div>
            """

        html_body += """
                <div class="footer">
                    Сообщение отправлено системой мониторинга сайтов.
                    Не отвечайте на это письмо.
                </div>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_email
        msg['To'] = ', '.join(self.to_emails)

        # Текстовая версия
        text_body = (
            f"АЛЕРТ [{severity.upper()}]\n\n"
            f"Сайт: {domain}\n"
            f"Тип: {alert_type}\n"
            f"Описание: {description}\n"
            f"Время: {timestamp}\n"
        )
        if details:
            text_body += f"\nДетали:\n{details}\n"
        if recommendation:
            text_body += f"\nРекомендация: {recommendation}\n"

        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                use_tls=self.use_tls
            )
            logger.info(f"Email alert sent for {domain} to {self.to_emails}")
        except Exception as e:
            logger.error(f"Email send error: {e}")

    async def send_daily_report(self, report_html: str, report_text: str):
        """Отправка ежедневного отчёта"""
        timestamp = datetime.now().strftime('%Y-%m-%d')
        subject = f"Ежедневный отчёт мониторинга сайтов — {timestamp}"

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_email
        msg['To'] = ', '.join(self.to_emails)

        msg.attach(MIMEText(report_text, 'plain', 'utf-8'))
        msg.attach(MIMEText(report_html, 'html', 'utf-8'))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_user,
                password=self.smtp_password,
                use_tls=self.use_tls
            )
            logger.info("Daily report email sent")
        except Exception as e:
            logger.error(f"Daily report email error: {e}")

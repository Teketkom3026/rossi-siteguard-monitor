"""
Firebase Cloud Messaging (FCM) push notification sender.
Sends push notifications to Android devices via Firebase.
"""
import logging
from typing import Optional, Dict, List

import firebase_admin
from firebase_admin import credentials, messaging

from app.config import settings

logger = logging.getLogger(__name__)


class FirebasePushSender:
    """
    Firebase Cloud Messaging push notification sender.

    Initializes the Firebase Admin SDK and provides methods to send
    notifications to individual devices or topics.
    """

    def __init__(self):
        self._initialized = False
        self._app = None

    def _ensure_initialized(self) -> bool:
        """
        Lazy-initialize Firebase Admin SDK.
        Returns True if initialized successfully, False otherwise.
        """
        if self._initialized:
            return True

        cred_path = settings.FIREBASE_CREDENTIALS_PATH
        if not cred_path:
            logger.warning(
                "FIREBASE_CREDENTIALS_PATH not set. "
                "Push notifications are disabled."
            )
            return False

        try:
            cred = credentials.Certificate(cred_path)
            self._app = firebase_admin.initialize_app(cred)
            self._initialized = True
            logger.info("Firebase Admin SDK initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            return False

    async def send_push(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send a push notification to a single device.

        Args:
            token: FCM device registration token.
            title: Notification title.
            body: Notification body text.
            data: Optional data payload (key-value string pairs).
            image_url: Optional image URL for rich notifications.

        Returns:
            Message ID string on success, None on failure.
        """
        if not self._ensure_initialized():
            return None

        if not token:
            logger.warning("Cannot send push: empty FCM token.")
            return None

        try:
            notification = messaging.Notification(
                title=title,
                body=body,
                image=image_url,
            )

            android_config = messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    icon="ic_notification",
                    color="#FF6B35",
                    sound="default",
                    channel_id="siteguard_alerts",
                    click_action="OPEN_DASHBOARD",
                ),
            )

            message = messaging.Message(
                notification=notification,
                android=android_config,
                data=data or {},
                token=token,
            )

            response = messaging.send(message)
            logger.info(
                f"Push sent successfully. Message ID: {response}"
            )
            return response

        except messaging.UnregisteredError:
            logger.warning(
                f"FCM token is no longer valid: {token[:20]}..."
            )
            return None
        except messaging.SenderIdMismatchError:
            logger.error("FCM sender ID mismatch. Check credentials.")
            return None
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return None

    async def send_push_to_multiple(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Dict[str, int]:
        """
        Send a push notification to multiple devices.

        Args:
            tokens: List of FCM device registration tokens.
            title: Notification title.
            body: Notification body text.
            data: Optional data payload.

        Returns:
            Dict with 'success' and 'failure' counts.
        """
        if not self._ensure_initialized():
            return {"success": 0, "failure": len(tokens)}

        if not tokens:
            return {"success": 0, "failure": 0}

        try:
            notification = messaging.Notification(
                title=title,
                body=body,
            )

            message = messaging.MulticastMessage(
                notification=notification,
                data=data or {},
                tokens=tokens,
            )

            response = messaging.send_each_for_multicast(message)

            logger.info(
                f"Multicast push: {response.success_count} sent, "
                f"{response.failure_count} failed"
            )

            return {
                "success": response.success_count,
                "failure": response.failure_count,
            }

        except Exception as e:
            logger.error(f"Failed to send multicast push: {e}")
            return {"success": 0, "failure": len(tokens)}

    async def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Send a push notification to a topic.

        Args:
            topic: FCM topic name (e.g. 'site_alerts', 'maintenance').
            title: Notification title.
            body: Notification body text.
            data: Optional data payload.

        Returns:
            Message ID on success, None on failure.
        """
        if not self._ensure_initialized():
            return None

        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                topic=topic,
            )

            response = messaging.send(message)
            logger.info(
                f"Topic push sent to '{topic}'. Message ID: {response}"
            )
            return response

        except Exception as e:
            logger.error(f"Failed to send topic push: {e}")
            return None

    async def send_site_alert(
        self,
        token: str,
        site_domain: str,
        alert_type: str,
        severity: str,
        message_text: str,
    ) -> Optional[str]:
        """
        Convenience method: send a site monitoring alert.

        Args:
            token: FCM device token.
            site_domain: Domain that triggered the alert.
            alert_type: Type of alert (e.g. 'availability', 'ssl', 'security').
            severity: Severity level ('critical', 'high', 'medium', 'low').
            message_text: Human-readable alert message.

        Returns:
            Message ID on success, None on failure.
        """
        severity_emoji = {
            "critical": "!!",
            "high": "!",
            "medium": "~",
            "low": "-",
        }

        indicator = severity_emoji.get(severity, "-")
        title = f"[{indicator}] {site_domain} - {alert_type}"

        data = {
            "type": "site_alert",
            "domain": site_domain,
            "alert_type": alert_type,
            "severity": severity,
        }

        return await self.send_push(
            token=token,
            title=title,
            body=message_text,
            data=data,
        )


# Module-level singleton
firebase_push = FirebasePushSender()

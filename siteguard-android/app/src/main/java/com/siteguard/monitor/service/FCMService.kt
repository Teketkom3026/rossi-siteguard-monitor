package com.siteguard.monitor.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.RingtoneManager
import android.os.Build
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.siteguard.monitor.R
import com.siteguard.monitor.ui.MainActivity
import com.siteguard.monitor.data.local.PreferencesManager
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class FCMService : FirebaseMessagingService() {

    @Inject
    lateinit var preferencesManager: PreferencesManager

    companion object {
        private const val CHANNEL_CRITICAL = "siteguard_critical"
        private const val CHANNEL_HIGH = "siteguard_high"
        private const val CHANNEL_MEDIUM = "siteguard_medium"
        private const val CHANNEL_INFO = "siteguard_info"
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        // Save and send to server
        CoroutineScope(Dispatchers.IO).launch {
            preferencesManager.saveFcmToken(token)
            // TODO: send token to backend
        }
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)

        val data = remoteMessage.data
        val severity = data["severity"] ?: "info"
        val domain = data["domain"] ?: ""
        val title = data["title"] ?: remoteMessage.notification?.title ?: "SiteGuard"
        val body = data["body"] ?: remoteMessage.notification?.body ?: ""
        val alertType = data["alert_type"] ?: ""

        sendNotification(
            title = title,
            body = body,
            severity = severity,
            domain = domain,
            alertType = alertType
        )
    }

    private fun sendNotification(
        title: String,
        body: String,
        severity: String,
        domain: String,
        alertType: String
    ) {
        val notificationManager = getSystemService(
            Context.NOTIFICATION_SERVICE
        ) as NotificationManager

        createNotificationChannels(notificationManager)

        // Choose channel by severity
        val channelId = when (severity) {
            "critical" -> CHANNEL_CRITICAL
            "high" -> CHANNEL_HIGH
            "medium" -> CHANNEL_MEDIUM
            else -> CHANNEL_INFO
        }

        // Emoji by severity
        val emoji = when (severity) {
            "critical" -> "\uD83D\uDD34"
            "high" -> "\uD83D\uDFE0"
            "medium" -> "\uD83D\uDFE1"
            "low" -> "\uD83D\uDD35"
            else -> "\u2139\uFE0F"
        }

        // Intent to open the app
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
            putExtra("domain", domain)
            putExtra("severity", severity)
        }

        val pendingIntent = PendingIntent.getActivity(
            this, domain.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or
            PendingIntent.FLAG_IMMUTABLE
        )

        // Sound
        val defaultSound = RingtoneManager.getDefaultUri(
            RingtoneManager.TYPE_NOTIFICATION
        )

        val notification = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("$emoji $title")
            .setContentText(body)
            .setStyle(
                NotificationCompat.BigTextStyle().bigText(body)
            )
            .setAutoCancel(true)
            .setSound(defaultSound)
            .setContentIntent(pendingIntent)
            .setPriority(
                when (severity) {
                    "critical" -> NotificationCompat.PRIORITY_MAX
                    "high" -> NotificationCompat.PRIORITY_HIGH
                    "medium" -> NotificationCompat.PRIORITY_DEFAULT
                    else -> NotificationCompat.PRIORITY_LOW
                }
            )
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .build()

        // Unique ID for each domain + alert type
        val notificationId = "$domain:$alertType".hashCode()
        notificationManager.notify(notificationId, notification)
    }

    private fun createNotificationChannels(
        manager: NotificationManager
    ) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channels = listOf(
                NotificationChannel(
                    CHANNEL_CRITICAL,
                    "Critical Alerts",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Site down, malware, SSL expired"
                    enableVibration(true)
                    vibrationPattern = longArrayOf(0, 500, 200, 500)
                },
                NotificationChannel(
                    CHANNEL_HIGH,
                    "Important Alerts",
                    NotificationManager.IMPORTANCE_HIGH
                ).apply {
                    description = "Buttons broken, SSL expiring soon"
                    enableVibration(true)
                },
                NotificationChannel(
                    CHANNEL_MEDIUM,
                    "Warnings",
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "Slow response, missing headers"
                },
                NotificationChannel(
                    CHANNEL_INFO,
                    "Informational",
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = "Recovery notifications, reports"
                }
            )

            channels.forEach { manager.createNotificationChannel(it) }
        }
    }
}

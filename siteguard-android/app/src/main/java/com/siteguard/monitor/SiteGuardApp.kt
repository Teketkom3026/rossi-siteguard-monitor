package com.siteguard.monitor

import android.app.Application
import com.siteguard.monitor.di.AppModule
import com.siteguard.monitor.service.PushNotificationService

class SiteGuardApp : Application() {
    override fun onCreate() {
        super.onCreate()
        AppModule.init(this)
        PushNotificationService.createNotificationChannel(this)
    }
}


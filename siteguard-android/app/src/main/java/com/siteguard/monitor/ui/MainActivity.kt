package com.siteguard.monitor.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.navigation.compose.rememberNavController
import com.siteguard.monitor.di.AppModule
import com.siteguard.monitor.ui.navigation.SiteGuardNavGraph
import com.siteguard.monitor.ui.theme.DarkBackground
import com.siteguard.monitor.ui.theme.SiteGuardTheme
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        val splashScreen = installSplashScreen()
        super.onCreate(savedInstanceState)

        val preferencesManager = AppModule.providePreferencesManager()

        // Check first run
        val isFirstRun = runBlocking {
            preferencesManager.isFirstRun.first()
        }

        setContent {
            SiteGuardTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = DarkBackground
                ) {
                    val navController = rememberNavController()
                    SiteGuardNavGraph(
                        navController = navController,
                        isFirstRun = isFirstRun
                    )
                }
            }
        }
    }
}

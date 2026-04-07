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
import com.siteguard.monitor.data.local.PreferencesManager
import com.siteguard.monitor.ui.navigation.SiteGuardNavGraph
import com.siteguard.monitor.ui.theme.DarkBackground
import com.siteguard.monitor.ui.theme.SiteGuardTheme
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var preferencesManager: PreferencesManager

    override fun onCreate(savedInstanceState: Bundle?) {
        val splashScreen = installSplashScreen()
        super.onCreate(savedInstanceState)

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

package com.siteguard.monitor.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.siteguard.monitor.ui.screens.setup.*
import com.siteguard.monitor.ui.screens.dashboard.DashboardScreen
import com.siteguard.monitor.ui.screens.detail.SiteDetailScreen
import com.siteguard.monitor.ui.screens.alerts.AlertsScreen
import com.siteguard.monitor.ui.screens.settings.SettingsScreen
import com.siteguard.monitor.ui.screens.settings.LicenseInfoScreen

sealed class Screen(val route: String) {
    object Setup : Screen("setup")
    object License : Screen("setup/license")
    object NotificationSetup : Screen("setup/notifications")
    object AddSites : Screen("setup/sites")
    object SetupComplete : Screen("setup/complete")
    object Dashboard : Screen("dashboard")
    object SiteDetail : Screen("site/{siteId}") {
        fun createRoute(siteId: Int) = "site/$siteId"
    }
    object Alerts : Screen("alerts")
    object Settings : Screen("settings")
    object LicenseInfo : Screen("settings/license")
}

@Composable
fun SiteGuardNavGraph(
    navController: NavHostController,
    isFirstRun: Boolean
) {
    val startDestination = if (isFirstRun) {
        Screen.License.route
    } else {
        Screen.Dashboard.route
    }

    NavHost(
        navController = navController,
        startDestination = startDestination
    ) {
        // ===== Setup Flow =====
        composable(Screen.License.route) {
            LicenseScreen(
                onLicenseActivated = {
                    navController.navigate(Screen.NotificationSetup.route)
                },
                onTrialStarted = {
                    navController.navigate(Screen.NotificationSetup.route)
                }
            )
        }

        composable(Screen.NotificationSetup.route) {
            NotificationSetupScreen(
                onNext = {
                    navController.navigate(Screen.AddSites.route)
                }
            )
        }

        composable(Screen.AddSites.route) {
            AddSitesScreen(
                onNext = {
                    navController.navigate(Screen.SetupComplete.route)
                }
            )
        }

        composable(Screen.SetupComplete.route) {
            SetupCompleteScreen(
                onFinish = {
                    navController.navigate(Screen.Dashboard.route) {
                        popUpTo(Screen.License.route) {
                            inclusive = true
                        }
                    }
                }
            )
        }

        // ===== Main App =====
        composable(Screen.Dashboard.route) {
            DashboardScreen(
                onSiteClick = { siteId ->
                    navController.navigate(
                        Screen.SiteDetail.createRoute(siteId)
                    )
                },
                onAlertsClick = {
                    navController.navigate(Screen.Alerts.route)
                },
                onSettingsClick = {
                    navController.navigate(Screen.Settings.route)
                }
            )
        }

        composable(
            route = Screen.SiteDetail.route,
            arguments = listOf(
                navArgument("siteId") { type = NavType.IntType }
            )
        ) { backStackEntry ->
            val siteId = backStackEntry.arguments?.getInt("siteId") ?: 0
            SiteDetailScreen(
                siteId = siteId,
                onBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Alerts.route) {
            AlertsScreen(
                onBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Settings.route) {
            SettingsScreen(
                onBack = { navController.popBackStack() },
                onLicenseClick = {
                    navController.navigate(Screen.LicenseInfo.route)
                }
            )
        }

        composable(Screen.LicenseInfo.route) {
            LicenseInfoScreen(
                onBack = { navController.popBackStack() }
            )
        }
    }
}

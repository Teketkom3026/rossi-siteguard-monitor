package com.siteguard.monitor.ui.screens.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.siteguard.monitor.data.api.models.DashboardResponse
import com.siteguard.monitor.data.api.models.SiteStatusResponse
import com.siteguard.monitor.data.repository.MonitorRepository
import com.siteguard.monitor.di.AppModule
import com.siteguard.monitor.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

// ===== ViewModel =====

data class DashboardUiState(
    val isLoading: Boolean = true,
    val isRefreshing: Boolean = false,
    val dashboard: DashboardResponse? = null,
    val errorMessage: String? = null
)

class DashboardViewModel(
    private val monitorRepository: MonitorRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        loadDashboard()
        startAutoRefresh()
    }

    fun loadDashboard() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val dashboard = monitorRepository.getDashboard()
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    dashboard = dashboard,
                    errorMessage = null
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    errorMessage = "Loading error: ${e.localizedMessage}"
                )
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isRefreshing = true)
            try {
                val dashboard = monitorRepository.getDashboard()
                _uiState.value = _uiState.value.copy(
                    isRefreshing = false,
                    dashboard = dashboard,
                    errorMessage = null
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isRefreshing = false,
                    errorMessage = e.localizedMessage
                )
            }
        }
    }

    fun checkAllNow() {
        viewModelScope.launch {
            try {
                monitorRepository.checkAllNow()
                delay(5000)
                refresh()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Error: ${e.localizedMessage}"
                )
            }
        }
    }

    private fun startAutoRefresh() {
        viewModelScope.launch {
            while (isActive) {
                delay(30_000) // 30 seconds
                try {
                    val dashboard = monitorRepository.getDashboard()
                    _uiState.value = _uiState.value.copy(
                        dashboard = dashboard,
                        errorMessage = null
                    )
                } catch (_: Exception) { }
            }
        }
    }

    companion object {
        val Factory: ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return DashboardViewModel(AppModule.provideMonitorRepository()) as T
            }
        }
    }
}

// ===== Composable Screen =====

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onSiteClick: (Int) -> Unit,
    onAlertsClick: () -> Unit,
    onSettingsClick: () -> Unit,
    viewModel: DashboardViewModel = viewModel(factory = DashboardViewModel.Factory)
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("\uD83D\uDEE1\uFE0F", fontSize = 24.sp)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "SiteGuard",
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                },
                actions = {
                    // Refresh button
                    IconButton(onClick = { viewModel.refresh() }) {
                        Icon(
                            Icons.Default.Refresh,
                            contentDescription = "Refresh",
                            tint = Color.White
                        )
                    }
                    // Check all button
                    IconButton(onClick = { viewModel.checkAllNow() }) {
                        Icon(
                            Icons.Default.PlayArrow,
                            contentDescription = "Check All",
                            tint = AccentBlue
                        )
                    }
                    // Alerts
                    IconButton(onClick = onAlertsClick) {
                        BadgedBox(
                            badge = {
                                val issues = uiState.dashboard?.sitesWithIssues ?: 0
                                if (issues > 0) {
                                    Badge(
                                        containerColor = ErrorRed
                                    ) {
                                        Text("$issues")
                                    }
                                }
                            }
                        ) {
                            Icon(
                                Icons.Default.Notifications,
                                contentDescription = "Alerts",
                                tint = Color.White
                            )
                        }
                    }
                    // Settings
                    IconButton(onClick = onSettingsClick) {
                        Icon(
                            Icons.Default.Settings,
                            contentDescription = "Settings",
                            tint = Color.White
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = DarkBackground
                )
            )
        },
        containerColor = DarkBackground
    ) { paddingValues ->

        if (uiState.isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = AccentBlue)
            }
            return@Scaffold
        }

        uiState.errorMessage?.let { error ->
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(
                        Icons.Default.CloudOff,
                        contentDescription = null,
                        tint = ErrorRed,
                        modifier = Modifier.size(64.dp)
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(error, color = ErrorRed, fontSize = 16.sp)
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(onClick = { viewModel.loadDashboard() }) {
                        Text("Retry")
                    }
                }
            }
            return@Scaffold
        }

        val dashboard = uiState.dashboard ?: return@Scaffold

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Stats
            item {
                Spacer(modifier = Modifier.height(8.dp))
                StatsRow(dashboard)
            }

            // Pull-to-refresh indicator
            if (uiState.isRefreshing) {
                item {
                    LinearProgressIndicator(
                        modifier = Modifier.fillMaxWidth(),
                        color = AccentBlue,
                        trackColor = DarkCard
                    )
                }
            }

            // List header
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "Sites (${dashboard.totalSites})",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    // Filter
                    var showOnlyIssues by remember { mutableStateOf(false) }
                    FilterChip(
                        selected = showOnlyIssues,
                        onClick = { showOnlyIssues = !showOnlyIssues },
                        label = { Text("Issues Only") },
                        leadingIcon = {
                            Icon(
                                Icons.Default.FilterList,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp)
                            )
                        },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = ErrorRed.copy(alpha = 0.2f),
                            selectedLabelColor = ErrorRed
                        )
                    )
                }
            }

            // Site list
            val sites = dashboard.sites
            items(sites) { site ->
                SiteCard(
                    site = site,
                    onClick = {
                        onSiteClick(sites.indexOf(site))
                    }
                )
            }

            item { Spacer(modifier = Modifier.height(16.dp)) }
        }
    }
}

// ===== Components =====

@Composable
fun StatsRow(dashboard: DashboardResponse) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        StatCard(
            modifier = Modifier.weight(1f),
            value = "${dashboard.totalSites}",
            label = "Total",
            color = AccentBlue,
            icon = Icons.Default.Language
        )
        StatCard(
            modifier = Modifier.weight(1f),
            value = "${dashboard.sitesOk}",
            label = "Online",
            color = SuccessGreen,
            icon = Icons.Default.CheckCircle
        )
        StatCard(
            modifier = Modifier.weight(1f),
            value = "${dashboard.sitesWithIssues}",
            label = "Issues",
            color = if (dashboard.sitesWithIssues > 0)
                ErrorRed else SuccessGreen,
            icon = Icons.Default.Error
        )
        StatCard(
            modifier = Modifier.weight(1f),
            value = "${dashboard.avgSecurityScore.toInt()}",
            label = "Security",
            color = when {
                dashboard.avgSecurityScore >= 75 -> SuccessGreen
                dashboard.avgSecurityScore >= 50 -> WarningOrange
                else -> ErrorRed
            },
            icon = Icons.Default.Shield
        )
    }
}

@Composable
fun StatCard(
    modifier: Modifier = Modifier,
    value: String,
    label: String,
    color: Color,
    icon: androidx.compose.ui.graphics.vector.ImageVector
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = DarkCard
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                icon,
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(20.dp)
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = value,
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
                color = color
            )
            Text(
                text = label,
                fontSize = 11.sp,
                color = Color.White.copy(alpha = 0.5f)
            )
        }
    }
}

@Composable
fun SiteCard(
    site: SiteStatusResponse,
    onClick: () -> Unit
) {
    val severityColor = when (site.overallSeverity) {
        "critical" -> ErrorRed
        "high" -> WarningOrange
        "medium" -> WarningYellow
        "low" -> AccentBlue
        else -> SuccessGreen
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = DarkCard
        )
    ) {
        Column {
            // Severity bar at top
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .background(severityColor)
            )

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Status indicator
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .clip(CircleShape)
                        .background(
                            if (site.isAvailable) SuccessGreen
                            else ErrorRed
                        )
                )

                Spacer(modifier = Modifier.width(12.dp))

                // Main info
                Column(modifier = Modifier.weight(1f)) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = site.domain,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )

                        // Malware badge
                        if (site.malwareDetected == true) {
                            Spacer(modifier = Modifier.width(8.dp))
                            Surface(
                                shape = RoundedCornerShape(4.dp),
                                color = ErrorRed.copy(alpha = 0.2f)
                            ) {
                                Text(
                                    text = "\uD83E\uDDA0 MALWARE",
                                    modifier = Modifier.padding(
                                        horizontal = 6.dp,
                                        vertical = 2.dp
                                    ),
                                    fontSize = 10.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = ErrorRed
                                )
                            }
                        }
                    }

                    // Issues
                    if (site.issues.isNotEmpty()) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "\u26A0\uFE0F ${site.issues.first().description}",
                            fontSize = 12.sp,
                            color = severityColor,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }

                Spacer(modifier = Modifier.width(8.dp))

                // Metrics on the right
                Column(
                    horizontalAlignment = Alignment.End
                ) {
                    // Response time
                    val responseMs = site.responseTimeMs?.toInt() ?: 0
                    val responseColor = when {
                        responseMs > 3000 -> ErrorRed
                        responseMs > 1500 -> WarningOrange
                        else -> SuccessGreen
                    }
                    Text(
                        text = "${responseMs}ms",
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = responseColor
                    )

                    Spacer(modifier = Modifier.height(4.dp))

                    // SSL + Security in row
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        // SSL badge
                        val sslDays = site.sslDaysLeft
                        val sslColor = when {
                            sslDays == null -> Color.Gray
                            sslDays <= 7 -> ErrorRed
                            sslDays <= 30 -> WarningOrange
                            else -> SuccessGreen
                        }
                        MiniMetric(
                            icon = "\uD83D\uDD12",
                            value = if (sslDays != null) "${sslDays}d" else "\u2014",
                            color = sslColor
                        )

                        // Security badge
                        val secScore = site.securityScore ?: 0
                        val secColor = when {
                            secScore >= 75 -> SuccessGreen
                            secScore >= 50 -> WarningOrange
                            else -> ErrorRed
                        }
                        MiniMetric(
                            icon = "\uD83D\uDEE1",
                            value = "$secScore",
                            color = secColor
                        )

                        // UI badge
                        val uiOk = site.uiElementsOk ?: 0
                        val uiTotal = site.uiElementsTotal ?: 0
                        if (uiTotal > 0) {
                            val uiColor = if (uiOk == uiTotal)
                                SuccessGreen else WarningOrange
                            MiniMetric(
                                icon = "\uD83D\uDDB1",
                                value = "$uiOk/$uiTotal",
                                color = uiColor
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.width(8.dp))

                // Arrow
                Icon(
                    Icons.Default.ChevronRight,
                    contentDescription = null,
                    tint = Color.White.copy(alpha = 0.3f),
                    modifier = Modifier.size(20.dp)
                )
            }
        }
    }
}

@Composable
fun MiniMetric(
    icon: String,
    value: String,
    color: Color
) {
    Surface(
        shape = RoundedCornerShape(4.dp),
        color = color.copy(alpha = 0.15f)
    ) {
        Row(
            modifier = Modifier.padding(
                horizontal = 4.dp,
                vertical = 2.dp
            ),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text = icon, fontSize = 10.sp)
            Spacer(modifier = Modifier.width(2.dp))
            Text(
                text = value,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                color = color
            )
        }
    }
}

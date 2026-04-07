package com.siteguard.monitor.ui.screens.detail

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.siteguard.monitor.data.api.models.SiteStatusResponse
import com.siteguard.monitor.data.repository.MonitorRepository
import com.siteguard.monitor.ui.theme.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SiteDetailUiState(
    val isLoading: Boolean = true,
    val siteStatus: SiteStatusResponse? = null,
    val errorMessage: String? = null
)

@HiltViewModel
class SiteDetailViewModel @Inject constructor(
    private val monitorRepository: MonitorRepository,
    savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val siteId: Int = savedStateHandle["siteId"] ?: 0
    private val _uiState = MutableStateFlow(SiteDetailUiState())
    val uiState: StateFlow<SiteDetailUiState> = _uiState.asStateFlow()

    init {
        loadSiteStatus()
    }

    fun loadSiteStatus() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val status = monitorRepository.getSiteStatus(siteId)
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    siteStatus = status,
                    errorMessage = null
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    errorMessage = "Error loading site details: ${e.localizedMessage}"
                )
            }
        }
    }

    fun triggerCheck() {
        viewModelScope.launch {
            try {
                monitorRepository.triggerCheck(siteId)
                kotlinx.coroutines.delay(3000)
                loadSiteStatus()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    errorMessage = "Error: ${e.localizedMessage}"
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SiteDetailScreen(
    siteId: Int,
    onBack: () -> Unit,
    viewModel: SiteDetailViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        uiState.siteStatus?.domain ?: "Site Details",
                        color = Color.White,
                        fontWeight = FontWeight.Bold
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = Color.White)
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.triggerCheck() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = AccentBlue)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkBackground)
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
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.Error, contentDescription = null, tint = ErrorRed, modifier = Modifier.size(64.dp))
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(error, color = ErrorRed, fontSize = 16.sp)
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(onClick = { viewModel.loadSiteStatus() }) { Text("Retry") }
                }
            }
            return@Scaffold
        }

        val site = uiState.siteStatus ?: return@Scaffold

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            // Status card
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(containerColor = DarkCard)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(16.dp)
                                .background(
                                    if (site.isAvailable) SuccessGreen else ErrorRed,
                                    RoundedCornerShape(8.dp)
                                )
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = if (site.isAvailable) "Online" else "Offline",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (site.isAvailable) SuccessGreen else ErrorRed
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))
                    DetailRow("HTTP Status", "${site.httpStatus ?: "N/A"}")
                    DetailRow("Response Time", "${site.responseTimeMs?.toInt() ?: 0}ms")
                    DetailRow("SSL Valid", if (site.sslValid == true) "Yes" else "No")
                    DetailRow("SSL Days Left", "${site.sslDaysLeft ?: "N/A"}")
                    DetailRow("Security Score", "${site.securityScore ?: 0}/100")
                    DetailRow("Malware", if (site.malwareDetected == true) "DETECTED" else "Clean")
                    if (site.uiElementsTotal != null && site.uiElementsTotal > 0) {
                        DetailRow("UI Elements", "${site.uiElementsOk ?: 0}/${site.uiElementsTotal}")
                    }
                    DetailRow("Last Check", site.lastCheckAt ?: "Never")
                }
            }

            // Issues
            if (site.issues.isNotEmpty()) {
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = "Issues (${site.issues.size})",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )
                Spacer(modifier = Modifier.height(8.dp))
                site.issues.forEach { issue ->
                    val issueColor = when (issue.severity) {
                        "critical" -> ErrorRed
                        "high" -> WarningOrange
                        "medium" -> WarningYellow
                        else -> AccentBlue
                    }
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp),
                        shape = RoundedCornerShape(8.dp),
                        colors = CardDefaults.cardColors(containerColor = DarkCard)
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .background(issueColor, RoundedCornerShape(4.dp))
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Column {
                                Text(
                                    text = issue.type.uppercase(),
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = issueColor
                                )
                                Text(
                                    text = issue.description,
                                    fontSize = 14.sp,
                                    color = Color.White.copy(alpha = 0.8f)
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(text = label, color = Color.White.copy(alpha = 0.6f), fontSize = 14.sp)
        Text(text = value, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 14.sp)
    }
}

package com.siteguard.monitor.ui.screens.setup

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.siteguard.monitor.data.repository.LicenseRepository
import com.siteguard.monitor.di.AppModule
import com.siteguard.monitor.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// ===== ViewModel =====

data class LicenseUiState(
    val licenseKey: String = "",
    val isLoading: Boolean = false,
    val isActivated: Boolean = false,
    val errorMessage: String? = null,
    val plan: String? = null,
    val maxSites: Int = 0,
    val daysRemaining: Int = 0,
    val features: Map<String, Boolean> = emptyMap()
)

class LicenseViewModel(
    private val licenseRepository: LicenseRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(LicenseUiState())
    val uiState: StateFlow<LicenseUiState> = _uiState.asStateFlow()

    fun updateLicenseKey(key: String) {
        _uiState.value = _uiState.value.copy(
            licenseKey = key.uppercase().take(35),
            errorMessage = null
        )
    }

    fun activateLicense() {
        val key = _uiState.value.licenseKey.trim()
        if (key.isEmpty()) {
            _uiState.value = _uiState.value.copy(
                errorMessage = "Please enter a license key"
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val result = licenseRepository.activateLicense(key)
                if (result.isValid) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isActivated = true,
                        errorMessage = null,
                        plan = result.plan,
                        maxSites = result.maxSites ?: 0,
                        daysRemaining = result.daysRemaining ?: 0,
                        features = result.features ?: emptyMap()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = result.message
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    errorMessage = "Connection error: ${e.localizedMessage}"
                )
            }
        }
    }

    fun startTrial() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)
            try {
                val result = licenseRepository.startTrial()
                if (result.isValid) {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isActivated = true,
                        errorMessage = null,
                        plan = "TRIAL",
                        maxSites = result.maxSites ?: 3,
                        daysRemaining = result.daysRemaining ?: 14,
                        features = result.features ?: emptyMap()
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        errorMessage = result.message
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    errorMessage = "Error: ${e.localizedMessage}"
                )
            }
        }
    }

    companion object {
        val Factory: ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return LicenseViewModel(AppModule.provideLicenseRepository()) as T
            }
        }
    }
}

// ===== Composable Screen =====

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LicenseScreen(
    onLicenseActivated: () -> Unit,
    onTrialStarted: () -> Unit,
    viewModel: LicenseViewModel = viewModel(factory = LicenseViewModel.Factory)
) {
    val uiState by viewModel.uiState.collectAsState()

    // Auto-navigate after activation
    LaunchedEffect(uiState.isActivated) {
        if (uiState.isActivated) {
            if (uiState.plan == "TRIAL") {
                onTrialStarted()
            } else {
                onLicenseActivated()
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(40.dp))

        // Logo
        Text(
            text = "\uD83D\uDEE1\uFE0F",
            fontSize = 64.sp
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Title
        Text(
            text = "SiteGuard Monitor",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold,
            color = Color.White
        )

        Text(
            text = "Site Monitoring 24/7",
            fontSize = 16.sp,
            color = Color.White.copy(alpha = 0.6f)
        )

        Spacer(modifier = Modifier.height(40.dp))

        // License key input card
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(
                containerColor = DarkCard
            )
        ) {
            Column(
                modifier = Modifier.padding(20.dp)
            ) {
                Text(
                    text = "\uD83D\uDD11 License Activation",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color.White
                )

                Spacer(modifier = Modifier.height(16.dp))

                // Key input field
                OutlinedTextField(
                    value = uiState.licenseKey,
                    onValueChange = { viewModel.updateLicenseKey(it) },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("License Key") },
                    placeholder = {
                        Text(
                            "SG-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX",
                            color = Color.White.copy(alpha = 0.3f)
                        )
                    },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        capitalization = KeyboardCapitalization.Characters,
                        keyboardType = KeyboardType.Ascii
                    ),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        focusedBorderColor = AccentBlue,
                        unfocusedBorderColor = Color.White.copy(alpha = 0.2f),
                        focusedLabelColor = AccentBlue,
                        unfocusedLabelColor = Color.White.copy(alpha = 0.5f),
                        cursorColor = AccentBlue
                    ),
                    leadingIcon = {
                        Icon(
                            Icons.Default.Key,
                            contentDescription = null,
                            tint = AccentBlue
                        )
                    }
                )

                Spacer(modifier = Modifier.height(16.dp))

                // Activate button
                Button(
                    onClick = { viewModel.activateLicense() },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = AccentBlue
                    ),
                    enabled = !uiState.isLoading &&
                              uiState.licenseKey.isNotEmpty()
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            color = Color.White,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Checking...")
                    } else {
                        Icon(
                            Icons.Default.VpnKey,
                            contentDescription = null
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "Activate Key",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                // Error message
                uiState.errorMessage?.let { error ->
                    Spacer(modifier = Modifier.height(12.dp))
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = ErrorRed.copy(alpha = 0.15f)
                        )
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                Icons.Default.Error,
                                contentDescription = null,
                                tint = ErrorRed,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = error,
                                color = ErrorRed,
                                fontSize = 14.sp
                            )
                        }
                    }
                }

                // Activated license info
                if (uiState.isActivated) {
                    Spacer(modifier = Modifier.height(12.dp))
                    LicenseInfoCard(uiState)
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Divider
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Divider(
                modifier = Modifier.weight(1f),
                color = Color.White.copy(alpha = 0.1f)
            )
            Text(
                text = "  or  ",
                color = Color.White.copy(alpha = 0.4f),
                fontSize = 14.sp
            )
            Divider(
                modifier = Modifier.weight(1f),
                color = Color.White.copy(alpha = 0.1f)
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Trial button
        OutlinedButton(
            onClick = { viewModel.startTrial() },
            modifier = Modifier
                .fillMaxWidth()
                .height(52.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.outlinedButtonColors(
                contentColor = SuccessGreen
            ),
            enabled = !uiState.isLoading
        ) {
            Icon(
                Icons.Default.CardGiftcard,
                contentDescription = null,
                tint = SuccessGreen
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = "Start Free Trial (14 days)",
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold,
                color = SuccessGreen
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Purchase link
        TextButton(
            onClick = {
                // Open purchase URL
            }
        ) {
            Text(
                text = "Buy a license \u2192",
                color = AccentBlue,
                fontSize = 14.sp
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        // Pricing cards
        PricingCards()
    }
}

@Composable
fun LicenseInfoCard(state: LicenseUiState) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(
            containerColor = SuccessGreen.copy(alpha = 0.15f)
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = null,
                    tint = SuccessGreen,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "License activated!",
                    color = SuccessGreen,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            InfoRow("Plan", state.plan?.uppercase() ?: "\u2014")
            InfoRow("Max Sites", "${state.maxSites}")
            InfoRow("Remaining", "${state.daysRemaining} days")

            Spacer(modifier = Modifier.height(8.dp))

            // Features
            val featureNames = mapOf(
                "availability_check" to "Availability",
                "ssl_check" to "SSL",
                "ui_tests" to "UI Tests",
                "security_scan" to "Security",
                "malware_scan" to "Antivirus"
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                state.features.forEach { (key, enabled) ->
                    featureNames[key]?.let { name ->
                        val bgColor = if (enabled)
                            SuccessGreen.copy(alpha = 0.2f)
                        else
                            ErrorRed.copy(alpha = 0.2f)
                        val textColor = if (enabled)
                            SuccessGreen
                        else
                            ErrorRed

                        Surface(
                            shape = RoundedCornerShape(20.dp),
                            color = bgColor
                        ) {
                            Text(
                                text = "${if (enabled) "\u2705" else "\u274C"} $name",
                                modifier = Modifier.padding(
                                    horizontal = 8.dp,
                                    vertical = 4.dp
                                ),
                                fontSize = 11.sp,
                                color = textColor
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun InfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            color = Color.White.copy(alpha = 0.6f),
            fontSize = 13.sp
        )
        Text(
            text = value,
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 13.sp
        )
    }
}

@Composable
fun PricingCards() {
    val plans = listOf(
        PricingPlan(
            "Starter",
            "2 990 \u20BD/year",
            "5 sites",
            listOf("Availability", "SSL", "UI Tests", "Export"),
            AccentBlue
        ),
        PricingPlan(
            "Professional",
            "9 990 \u20BD/year",
            "25 sites",
            listOf("All from Starter", "Security", "Antivirus", "API"),
            SuccessGreen
        ),
        PricingPlan(
            "Business",
            "29 990 \u20BD/year",
            "100 sites",
            listOf("All from Pro", "White-label", "Priority"),
            WarningOrange
        )
    )

    Text(
        text = "Pricing Plans",
        fontSize = 18.sp,
        fontWeight = FontWeight.Bold,
        color = Color.White,
        modifier = Modifier.padding(bottom = 12.dp)
    )

    plans.forEach { plan ->
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 6.dp),
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(
                containerColor = DarkCard
            )
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Color bar
                Box(
                    modifier = Modifier
                        .width(4.dp)
                        .height(60.dp)
                        .background(
                            plan.accentColor,
                            RoundedCornerShape(2.dp)
                        )
                )

                Spacer(modifier = Modifier.width(12.dp))

                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = plan.name,
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = plan.accentColor
                    )
                    Text(
                        text = plan.sitesLimit,
                        fontSize = 13.sp,
                        color = Color.White.copy(alpha = 0.6f)
                    )
                    Text(
                        text = plan.features.joinToString(" \u2022 "),
                        fontSize = 11.sp,
                        color = Color.White.copy(alpha = 0.4f)
                    )
                }

                Text(
                    text = plan.price,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    color = Color.White
                )
            }
        }
    }
}

data class PricingPlan(
    val name: String,
    val price: String,
    val sitesLimit: String,
    val features: List<String>,
    val accentColor: Color
)

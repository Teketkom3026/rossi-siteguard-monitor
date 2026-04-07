package com.siteguard.monitor.data.api.models

import com.google.gson.annotations.SerializedName

// ===== Site Models =====

data class AddSiteRequest(
    val domain: String,
    val name: String? = null,
    @SerializedName("check_interval") val checkInterval: Int = 300,
    val settings: Map<String, Any>? = null
)

data class UpdateSiteRequest(
    val name: String? = null,
    @SerializedName("check_interval") val checkInterval: Int? = null,
    @SerializedName("is_active") val isActive: Boolean? = null,
    val settings: Map<String, Any>? = null
)

data class SiteResponse(
    val id: Int,
    val domain: String,
    val name: String?,
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("check_interval") val checkInterval: Int,
    val settings: Map<String, Any>,
    @SerializedName("current_status") val currentStatus: Map<String, Any>,
    @SerializedName("last_check_at") val lastCheckAt: String?,
    @SerializedName("created_at") val createdAt: String
)

data class SiteStatusResponse(
    val domain: String,
    @SerializedName("is_available") val isAvailable: Boolean,
    @SerializedName("http_status") val httpStatus: Int?,
    @SerializedName("response_time_ms") val responseTimeMs: Float?,
    @SerializedName("ssl_valid") val sslValid: Boolean?,
    @SerializedName("ssl_days_left") val sslDaysLeft: Int?,
    @SerializedName("security_score") val securityScore: Int?,
    @SerializedName("malware_detected") val malwareDetected: Boolean?,
    @SerializedName("ui_elements_ok") val uiElementsOk: Int?,
    @SerializedName("ui_elements_total") val uiElementsTotal: Int?,
    @SerializedName("overall_severity") val overallSeverity: String,
    val issues: List<IssueItem>,
    @SerializedName("last_check_at") val lastCheckAt: String?,
    @SerializedName("sitemap_tree") val sitemapTree: Map<String, Any>?
)

data class IssueItem(
    val type: String,
    val severity: String,
    val description: String
)

data class DashboardResponse(
    @SerializedName("total_sites") val totalSites: Int,
    @SerializedName("sites_ok") val sitesOk: Int,
    @SerializedName("sites_with_issues") val sitesWithIssues: Int,
    @SerializedName("ssl_expiring") val sslExpiring: Int,
    @SerializedName("avg_security_score") val avgSecurityScore: Float,
    val sites: List<SiteStatusResponse>,
    @SerializedName("last_updated") val lastUpdated: String
)

data class AlertResponse(
    val id: Int,
    val domain: String,
    val timestamp: String,
    @SerializedName("alert_type") val alertType: String,
    val severity: String,
    val description: String,
    val details: String?,
    val recommendation: String?
)

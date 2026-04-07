package com.siteguard.monitor.data.api.models

import com.google.gson.annotations.SerializedName

// ===== License Models =====

data class LicenseActivateRequest(
    @SerializedName("license_key") val licenseKey: String,
    @SerializedName("device_id") val deviceId: String,
    @SerializedName("device_type") val deviceType: String = "android",
    @SerializedName("device_info") val deviceInfo: DeviceInfo? = null
)

data class DeviceInfo(
    val name: String,
    val os: String,
    val model: String,
    val manufacturer: String,
    @SerializedName("sdk_version") val sdkVersion: Int
)

data class LicenseActivateResponse(
    @SerializedName("is_valid") val isValid: Boolean,
    val message: String,
    val plan: String? = null,
    @SerializedName("max_sites") val maxSites: Int? = null,
    @SerializedName("expires_at") val expiresAt: String? = null,
    @SerializedName("days_remaining") val daysRemaining: Int? = null,
    val features: Map<String, Boolean>? = null,
    @SerializedName("sites_remaining") val sitesRemaining: Int? = null
)

data class LicensePlanResponse(
    val name: String,
    @SerializedName("display_name") val displayName: String,
    @SerializedName("max_sites") val maxSites: Int,
    val price: Double,
    @SerializedName("price_display") val priceDisplay: String,
    val features: Map<String, Boolean>,
    @SerializedName("duration_days") val durationDays: Int
)

data class LicenseInfoResponse(
    @SerializedName("license_key") val licenseKey: String,
    val plan: String,
    val status: String,
    @SerializedName("max_sites") val maxSites: Int,
    @SerializedName("sites_used") val sitesUsed: Int,
    @SerializedName("sites_remaining") val sitesRemaining: Int,
    @SerializedName("max_devices") val maxDevices: Int,
    @SerializedName("devices_used") val devicesUsed: Int,
    val features: Map<String, Boolean>,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("expires_at") val expiresAt: String,
    @SerializedName("days_remaining") val daysRemaining: Int
)

package com.siteguard.monitor.data.repository

import android.os.Build
import com.siteguard.monitor.data.api.LicenseApi
import com.siteguard.monitor.data.api.models.DeviceInfo
import com.siteguard.monitor.data.api.models.LicenseActivateRequest
import com.siteguard.monitor.data.api.models.LicenseActivateResponse
import com.siteguard.monitor.data.api.models.LicenseInfoResponse
import com.siteguard.monitor.data.api.models.LicensePlanResponse
import com.siteguard.monitor.data.local.PreferencesManager
import java.util.UUID

class LicenseRepository(
    private val api: LicenseApi,
    private val prefs: PreferencesManager
) {

    private suspend fun getOrCreateDeviceId(): String {
        val existing = prefs.getDeviceId()
        if (existing != null) return existing
        val newId = UUID.randomUUID().toString()
        prefs.saveDeviceId(newId)
        return newId
    }

    private fun getDeviceInfo(): DeviceInfo {
        return DeviceInfo(
            name = "${Build.MANUFACTURER} ${Build.MODEL}",
            os = "Android ${Build.VERSION.RELEASE}",
            model = Build.MODEL,
            manufacturer = Build.MANUFACTURER,
            sdkVersion = Build.VERSION.SDK_INT
        )
    }

    suspend fun activateLicense(licenseKey: String): LicenseActivateResponse {
        val deviceId = getOrCreateDeviceId()
        val request = LicenseActivateRequest(
            licenseKey = licenseKey,
            deviceId = deviceId,
            deviceType = "android",
            deviceInfo = getDeviceInfo()
        )
        val response = api.activateLicense(request)
        if (response.isSuccessful) {
            val body = response.body()!!
            if (body.isValid) {
                prefs.saveLicenseKey(licenseKey)
                prefs.setFirstRunComplete()
            }
            return body
        } else {
            throw Exception("Server error: ${response.code()}")
        }
    }

    suspend fun startTrial(): LicenseActivateResponse {
        val deviceId = getOrCreateDeviceId()
        val request = LicenseActivateRequest(
            licenseKey = "TRIAL",
            deviceId = deviceId,
            deviceType = "android",
            deviceInfo = getDeviceInfo()
        )
        val response = api.activateLicense(request)
        if (response.isSuccessful) {
            val body = response.body()!!
            if (body.isValid) {
                prefs.setFirstRunComplete()
            }
            return body
        } else {
            throw Exception("Server error: ${response.code()}")
        }
    }

    suspend fun validateLicense(): LicenseActivateResponse {
        val deviceId = getOrCreateDeviceId()
        val request = LicenseActivateRequest(
            licenseKey = "",
            deviceId = deviceId,
            deviceType = "android"
        )
        val response = api.validateLicense(request)
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Validation failed: ${response.code()}")
        }
    }

    suspend fun getLicenseInfo(): LicenseInfoResponse {
        val response = api.getLicenseInfo()
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Failed to get license info: ${response.code()}")
        }
    }

    suspend fun getPlans(): List<LicensePlanResponse> {
        val response = api.getPlans()
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Failed to get plans: ${response.code()}")
        }
    }
}

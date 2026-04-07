package com.siteguard.monitor.data.repository

import com.siteguard.monitor.data.api.MonitorApi
import com.siteguard.monitor.data.api.models.*
import com.siteguard.monitor.data.local.PreferencesManager

class MonitorRepository(
    private val api: MonitorApi,
    private val prefs: PreferencesManager
) {

    suspend fun getDashboard(): DashboardResponse {
        val response = api.getDashboard()
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Failed to load dashboard: ${response.code()}")
        }
    }

    suspend fun addSite(domain: String, name: String? = null, checkInterval: Int = 300): SiteResponse {
        val request = AddSiteRequest(
            domain = domain,
            name = name,
            checkInterval = checkInterval
        )
        val response = api.addSite(request)
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Failed to add site: ${response.code()}")
        }
    }

    suspend fun listSites(): List<SiteResponse> {
        val response = api.listSites()
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Failed to list sites: ${response.code()}")
        }
    }

    suspend fun updateSite(siteId: Int, request: UpdateSiteRequest): SiteResponse {
        val response = api.updateSite(siteId, request)
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Failed to update site: ${response.code()}")
        }
    }

    suspend fun deleteSite(siteId: Int) {
        val response = api.deleteSite(siteId)
        if (!response.isSuccessful) {
            throw Exception("Failed to delete site: ${response.code()}")
        }
    }

    suspend fun getSiteStatus(siteId: Int): SiteStatusResponse {
        val response = api.getSiteStatus(siteId)
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Failed to get site status: ${response.code()}")
        }
    }

    suspend fun triggerCheck(siteId: Int) {
        val response = api.triggerCheck(siteId)
        if (!response.isSuccessful) {
            throw Exception("Failed to trigger check: ${response.code()}")
        }
    }

    suspend fun checkAllNow() {
        val sites = listSites()
        sites.forEach { site ->
            try {
                triggerCheck(site.id)
            } catch (_: Exception) { }
        }
    }

    suspend fun getAlerts(limit: Int = 50, domain: String? = null): List<AlertResponse> {
        val response = api.getAlerts(limit, domain)
        if (response.isSuccessful) {
            return response.body()!!
        } else {
            throw Exception("Failed to get alerts: ${response.code()}")
        }
    }
}

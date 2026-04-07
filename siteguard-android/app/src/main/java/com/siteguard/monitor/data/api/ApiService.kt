package com.siteguard.monitor.data.api

import com.siteguard.monitor.data.api.models.*
import retrofit2.Response
import retrofit2.http.*

interface LicenseApi {

    @POST("api/v1/license/activate")
    suspend fun activateLicense(
        @Body request: LicenseActivateRequest
    ): Response<LicenseActivateResponse>

    @POST("api/v1/license/validate")
    suspend fun validateLicense(
        @Body request: LicenseActivateRequest
    ): Response<LicenseActivateResponse>

    @GET("api/v1/license/info")
    suspend fun getLicenseInfo(): Response<LicenseInfoResponse>

    @GET("api/v1/license/plans")
    suspend fun getPlans(): Response<List<LicensePlanResponse>>

    @POST("api/v1/license/deactivate-device")
    suspend fun deactivateDevice(
        @Query("device_id") deviceId: String
    ): Response<Map<String, String>>
}

interface MonitorApi {

    @POST("api/v1/monitor/sites")
    suspend fun addSite(
        @Body request: AddSiteRequest
    ): Response<SiteResponse>

    @GET("api/v1/monitor/sites")
    suspend fun listSites(): Response<List<SiteResponse>>

    @PUT("api/v1/monitor/sites/{siteId}")
    suspend fun updateSite(
        @Path("siteId") siteId: Int,
        @Body request: UpdateSiteRequest
    ): Response<SiteResponse>

    @DELETE("api/v1/monitor/sites/{siteId}")
    suspend fun deleteSite(
        @Path("siteId") siteId: Int
    ): Response<Map<String, String>>

    @GET("api/v1/monitor/dashboard")
    suspend fun getDashboard(): Response<DashboardResponse>

    @GET("api/v1/monitor/sites/{siteId}/status")
    suspend fun getSiteStatus(
        @Path("siteId") siteId: Int
    ): Response<SiteStatusResponse>

    @POST("api/v1/monitor/sites/{siteId}/check-now")
    suspend fun triggerCheck(
        @Path("siteId") siteId: Int
    ): Response<Map<String, String>>

    @GET("api/v1/alerts")
    suspend fun getAlerts(
        @Query("limit") limit: Int = 50,
        @Query("domain") domain: String? = null
    ): Response<List<AlertResponse>>
}

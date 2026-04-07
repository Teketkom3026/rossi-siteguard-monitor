package com.siteguard.monitor.data.api

import com.siteguard.monitor.data.api.models.*
import retrofit2.Response
import retrofit2.http.*

interface ApiService {

    // --- License ---
    @POST("api/v1/license/activate")
    suspend fun activateLicense(@Body request: LicenseActivateRequest): Response<LicenseActivateResponse>

    @POST("api/v1/license/validate")
    suspend fun validateLicense(@Body request: LicenseActivateRequest): Response<LicenseActivateResponse>

    @GET("api/v1/license/info")
    suspend fun getLicenseInfo(): Response<LicenseInfoResponse>

    @GET("api/v1/license/plans")
    suspend fun getPlans(): Response<List<LicensePlanResponse>>

    // --- Monitor ---
    @GET("api/v1/dashboard")
    suspend fun getDashboard(): Response<DashboardResponse>

    @GET("api/v1/sites")
    suspend fun getSites(): Response<List<SiteResponse>>

    @GET("api/v1/sites")
    suspend fun listSites(): Response<List<SiteResponse>>

    @POST("api/v1/sites")
    suspend fun addSite(@Body request: AddSiteRequest): Response<SiteResponse>

    @PUT("api/v1/sites/{id}")
    suspend fun updateSite(@Path("id") id: Int, @Body request: UpdateSiteRequest): Response<SiteResponse>

    @DELETE("api/v1/sites/{id}")
    suspend fun deleteSite(@Path("id") id: Int): Response<Unit>

    @GET("api/v1/sites/{id}/status")
    suspend fun getSiteStatus(@Path("id") id: Int): Response<SiteStatusResponse>

    @POST("api/v1/sites/{id}/check")
    suspend fun triggerCheck(@Path("id") id: Int): Response<Unit>

    @GET("api/v1/alerts")
    suspend fun getAlerts(
        @Query("limit") limit: Int = 50,
        @Query("domain") domain: String? = null
    ): Response<List<AlertResponse>>
}

// Backward compatibility aliases
typealias LicenseApi = ApiService
typealias MonitorApi = ApiService

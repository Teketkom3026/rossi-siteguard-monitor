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
    @GET("api/v1/sites")
    suspend fun getSites(): Response<List<SiteResponse>>

    @POST("api/v1/sites")
    suspend fun addSite(@Body request: AddSiteRequest): Response<SiteResponse>

    @DELETE("api/v1/sites/{id}")
    suspend fun deleteSite(@Path("id") id: String): Response<Unit>

    @GET("api/v1/sites/{id}/status")
    suspend fun getSiteStatus(@Path("id") id: String): Response<SiteStatusResponse>

    @GET("api/v1/alerts")
    suspend fun getAlerts(): Response<List<AlertResponse>>
}

// Backward compatibility aliases
typealias LicenseApi = ApiService
typealias MonitorApi = ApiService


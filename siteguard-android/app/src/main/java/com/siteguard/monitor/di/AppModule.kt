package com.siteguard.monitor.di

import android.content.Context
import com.siteguard.monitor.BuildConfig
import com.siteguard.monitor.data.api.ApiService
import com.siteguard.monitor.data.local.PreferencesManager
import com.siteguard.monitor.data.repository.LicenseRepository
import com.siteguard.monitor.data.repository.MonitorRepository
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object AppModule {
    
    private val okHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        })
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL + "/")
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    private val apiService: ApiService = retrofit.create(ApiService::class.java)

    private lateinit var appContext: Context

    fun init(context: Context) {
        appContext = context.applicationContext
    }

    fun providePreferencesManager(): PreferencesManager = PreferencesManager(appContext)

    fun provideLicenseRepository(): LicenseRepository =
        LicenseRepository(apiService, providePreferencesManager())

    fun provideMonitorRepository(): MonitorRepository =
        MonitorRepository(apiService, providePreferencesManager())
}


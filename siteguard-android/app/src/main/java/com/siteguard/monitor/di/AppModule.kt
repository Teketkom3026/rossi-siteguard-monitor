package com.siteguard.monitor.di

import android.content.Context
import com.siteguard.monitor.BuildConfig
import com.siteguard.monitor.data.api.LicenseApi
import com.siteguard.monitor.data.api.MonitorApi
import com.siteguard.monitor.data.local.PreferencesManager
import com.siteguard.monitor.data.repository.LicenseRepository
import com.siteguard.monitor.data.repository.MonitorRepository
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun providePreferencesManager(
        @ApplicationContext context: Context
    ): PreferencesManager {
        return PreferencesManager(context)
    }

    @Provides
    @Singleton
    fun provideAuthInterceptor(
        prefsManager: PreferencesManager
    ): Interceptor {
        return Interceptor { chain ->
            val token = prefsManager.getAuthTokenSync()
            val request = chain.request().newBuilder()
                .apply {
                    if (token != null) {
                        addHeader("Authorization", "Bearer $token")
                    }
                    addHeader("X-App-Version", BuildConfig.VERSION_NAME)
                    addHeader("X-Platform", "android")
                }
                .build()
            chain.proceed(request)
        }
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        authInterceptor: Interceptor
    ): OkHttpClient {
        return OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(
                HttpLoggingInterceptor().apply {
                    level = if (BuildConfig.DEBUG)
                        HttpLoggingInterceptor.Level.BODY
                    else
                        HttpLoggingInterceptor.Level.NONE
                }
            )
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient): Retrofit {
        return Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    @Provides
    @Singleton
    fun provideLicenseApi(retrofit: Retrofit): LicenseApi {
        return retrofit.create(LicenseApi::class.java)
    }

    @Provides
    @Singleton
    fun provideMonitorApi(retrofit: Retrofit): MonitorApi {
        return retrofit.create(MonitorApi::class.java)
    }

    @Provides
    @Singleton
    fun provideLicenseRepository(
        api: LicenseApi,
        prefs: PreferencesManager
    ): LicenseRepository {
        return LicenseRepository(api, prefs)
    }

    @Provides
    @Singleton
    fun provideMonitorRepository(
        api: MonitorApi,
        prefs: PreferencesManager
    ): MonitorRepository {
        return MonitorRepository(api, prefs)
    }
}

package com.siteguard.monitor.data.local

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(
    name = "siteguard_prefs"
)

class PreferencesManager(private val context: Context) {

    companion object {
        private val KEY_AUTH_TOKEN = stringPreferencesKey("auth_token")
        private val KEY_LICENSE_KEY = stringPreferencesKey("license_key")
        private val KEY_FCM_TOKEN = stringPreferencesKey("fcm_token")
        private val KEY_IS_FIRST_RUN = booleanPreferencesKey("is_first_run")
        private val KEY_DEVICE_ID = stringPreferencesKey("device_id")
    }

    val isFirstRun: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[KEY_IS_FIRST_RUN] ?: true
    }

    val authToken: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[KEY_AUTH_TOKEN]
    }

    val licenseKey: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[KEY_LICENSE_KEY]
    }

    fun getAuthTokenSync(): String? {
        return runBlocking {
            context.dataStore.data.first()[KEY_AUTH_TOKEN]
        }
    }

    suspend fun saveAuthToken(token: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_AUTH_TOKEN] = token
        }
    }

    suspend fun saveLicenseKey(key: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_LICENSE_KEY] = key
        }
    }

    suspend fun saveFcmToken(token: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_FCM_TOKEN] = token
        }
    }

    suspend fun setFirstRunComplete() {
        context.dataStore.edit { prefs ->
            prefs[KEY_IS_FIRST_RUN] = false
        }
    }

    suspend fun saveDeviceId(deviceId: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_DEVICE_ID] = deviceId
        }
    }

    suspend fun getDeviceId(): String? {
        return context.dataStore.data.first()[KEY_DEVICE_ID]
    }

    suspend fun clearAll() {
        context.dataStore.edit { it.clear() }
    }
}

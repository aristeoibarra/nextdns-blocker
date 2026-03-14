package com.ndb.blocker

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray

class LauncherPrefs(context: Context) {

    companion object {
        private const val PREFS_NAME = "ndb_launcher"
        private const val KEY_FAVORITES = "favorites"
        private const val KEY_HIDDEN = "hidden_packages"
    }

    private val prefs: SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getFavorites(): List<String> {
        val json = prefs.getString(KEY_FAVORITES, null) ?: return emptyList()
        return try {
            val arr = JSONArray(json)
            (0 until arr.length()).map { arr.getString(it) }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun addFavorite(pkg: String) {
        val list = getFavorites().toMutableList()
        if (pkg !in list) {
            list.add(pkg)
            saveFavorites(list)
        }
    }

    fun removeFavorite(pkg: String) {
        val list = getFavorites().toMutableList()
        if (list.remove(pkg)) {
            saveFavorites(list)
        }
    }

    private fun saveFavorites(list: List<String>) {
        val arr = JSONArray()
        list.forEach { arr.put(it) }
        prefs.edit().putString(KEY_FAVORITES, arr.toString()).apply()
    }

    fun getHiddenPackages(): Set<String> {
        return prefs.getStringSet(KEY_HIDDEN, emptySet()) ?: emptySet()
    }

    fun hidePackage(pkg: String) {
        val set = getHiddenPackages().toMutableSet()
        set.add(pkg)
        prefs.edit().putStringSet(KEY_HIDDEN, set).apply()
    }

    fun unhidePackage(pkg: String) {
        val set = getHiddenPackages().toMutableSet()
        set.remove(pkg)
        prefs.edit().putStringSet(KEY_HIDDEN, set).apply()
    }

    fun registerListener(listener: SharedPreferences.OnSharedPreferenceChangeListener) {
        prefs.registerOnSharedPreferenceChangeListener(listener)
    }

    fun unregisterListener(listener: SharedPreferences.OnSharedPreferenceChangeListener) {
        prefs.unregisterOnSharedPreferenceChangeListener(listener)
    }
}

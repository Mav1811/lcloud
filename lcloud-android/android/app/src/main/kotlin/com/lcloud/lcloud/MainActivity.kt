package com.lcloud.lcloud

import android.content.Context
import android.net.wifi.WifiManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.lcloud.lcloud/multicast"
    private var multicastLock: WifiManager.MulticastLock? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "acquireLock" -> {
                        try {
                            val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                            multicastLock = wm.createMulticastLock("lcloud_mdns")
                            multicastLock?.setReferenceCounted(true)
                            multicastLock?.acquire()
                            result.success(null)
                        } catch (e: Exception) {
                            result.error("LOCK_ERROR", e.message, null)
                        }
                    }
                    "releaseLock" -> {
                        try {
                            multicastLock?.release()
                            multicastLock = null
                            result.success(null)
                        } catch (e: Exception) {
                            result.error("LOCK_ERROR", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }
}

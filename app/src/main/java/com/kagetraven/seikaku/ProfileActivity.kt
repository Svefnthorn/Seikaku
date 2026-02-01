package com.kagetraven.seikaku

import android.os.Bundle
import android.util.Log
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import okhttp3.*
import org.json.JSONObject
import java.io.IOException

class ProfileActivity : AppCompatActivity() {

    private val client = OkHttpClient()
    private val statsUrl = "https://jacinto-unsinuated-semiphenomenally.ngrok-free.dev/user/stats"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_profile)

        findViewById<ImageButton>(R.id.btnBack).setOnClickListener {
            finish()
        }

        fetchUserStats()
    }

    private fun fetchUserStats() {
        val request = Request.Builder()
            .url(statsUrl)
            .get()
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e("ProfileActivity", "Failed to fetch stats", e)
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!response.isSuccessful) {
                        Log.e("ProfileActivity", "Server error: ${response.code}")
                        return
                    }

                    val body = response.body?.string()
                    if (body != null) {
                        try {
                            val json = JSONObject(body)
                            val currentStreak = json.optInt("current_streak", 0)
                            val bestStreak = json.optInt("best_streak", 0)
                            val totalSessions = json.optInt("total_sessions", 0)
                            val userAverage = json.optDouble("user_average", 0.0)

                            runOnUiThread {
                                displayStats(currentStreak, bestStreak, totalSessions, userAverage)
                            }
                        } catch (e: Exception) {
                            Log.e("ProfileActivity", "JSON parsing error", e)
                        }
                    }
                }
            }
        })
    }

    private fun displayStats(currentStreak: Int, bestStreak: Int, totalSessions: Int, userAverage: Double) {
        findViewById<TextView>(R.id.tvCurrentStreak).text = currentStreak.toString()
        findViewById<TextView>(R.id.tvBestStreak).text = bestStreak.toString()
        findViewById<TextView>(R.id.tvTotalSessions).text = totalSessions.toString()
        findViewById<TextView>(R.id.tvAvgScore).text = String.format("%.1f", userAverage)
    }
}
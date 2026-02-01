package com.kagetraven.seikaku

import android.os.Bundle
import android.util.Log
import android.widget.ImageButton
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import okhttp3.*
import org.json.JSONArray
import java.io.IOException

class LeaderboardActivity : AppCompatActivity() {

    private val client = OkHttpClient()
    private val leaderboardUrl = "https://jacinto-unsinuated-semiphenomenally.ngrok-free.dev/leaderboard"
    private lateinit var rvLeaderboard: RecyclerView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_leaderboard)

        findViewById<ImageButton>(R.id.btnBack).setOnClickListener {
            finish()
        }

        rvLeaderboard = findViewById(R.id.rvLeaderboard)
        rvLeaderboard.layoutManager = LinearLayoutManager(this)

        fetchLeaderboard()
    }

    private fun fetchLeaderboard() {
        val request = Request.Builder()
            .url(leaderboardUrl)
            .get()
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                Log.e("LeaderboardActivity", "Failed to fetch leaderboard", e)
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!response.isSuccessful) {
                        Log.e("LeaderboardActivity", "Server error: ${response.code}")
                        return
                    }

                    val body = response.body?.string()
                    if (body != null) {
                        try {
                            val jsonArray = JSONArray(body)
                            val leaderboardList = mutableListOf<LeaderboardEntry>()
                            
                            for (i in 0 until jsonArray.length()) {
                                val obj = jsonArray.getJSONObject(i)
                                leaderboardList.add(
                                    LeaderboardEntry(
                                        name = obj.getString("name"),
                                        streak = obj.getInt("streak"),
                                        avgScore = obj.getDouble("avg_score")
                                    )
                                )
                            }

                            runOnUiThread {
                                rvLeaderboard.adapter = LeaderboardAdapter(leaderboardList)
                            }
                        } catch (e: Exception) {
                            Log.e("LeaderboardActivity", "JSON parsing error", e)
                        }
                    }
                }
            }
        })
    }
}
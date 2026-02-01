package com.kagetraven.seikaku

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.appcompat.app.AppCompatActivity
import com.kagetraven.seikaku.databinding.ActivityStartupBinding

class StartupActivity : AppCompatActivity() {

    private lateinit var binding: ActivityStartupBinding
    private val handler = Handler(Looper.getMainLooper())
    private val characters = listOf(
        "あ", "い", "う", "え", "お", 
        "カ", "キ", "ク", "ケ", "コ",
        "学", "生", "先", "生", "私",
        "日", "本", "語", "語", "友",
        "幸", "海", "山", "空", "花"
    )
    private var currentIndex = 0

    private val slideshowRunnable = object : Runnable {
        override fun run() {
            binding.textViewSlideshow.text = characters[currentIndex]
            currentIndex = (currentIndex + 1) % characters.size
            handler.postDelayed(this, 2000) // Change character every 2 seconds
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityStartupBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Reset completion status when the app starts
        val sharedPrefs = getSharedPreferences("SeikakuPrefs", Context.MODE_PRIVATE)
        sharedPrefs.edit().clear().apply()

        binding.btnLogin.setOnClickListener {
            // Logic for Log in could go here
        }

        binding.btnGuest.setOnClickListener {
            val intent = Intent(this, MainActivity::class.java)
            startActivity(intent)
            finish()
        }
        
        // Start slideshow
        handler.post(slideshowRunnable)
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacks(slideshowRunnable)
    }
}
package com.kagetraven.seikaku

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.kagetraven.seikaku.databinding.ActivityProgressTrackingBinding

class ProgressTrackingActivity : AppCompatActivity() {

    private lateinit var binding: ActivityProgressTrackingBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityProgressTrackingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val current = intent.getIntExtra("CURRENT", 0)
        val total = intent.getIntExtra("TOTAL", 1)
        val chapterTitle = intent.getStringExtra("CHAPTER_TITLE") ?: "Chapter"
        
        val progressPercent = (current.toFloat() / total.toFloat() * 100).toInt()
        
        binding.circularProgress.progress = progressPercent
        binding.textViewPercent.text = "$progressPercent%"
        
        if (progressPercent >= 100) {
            binding.textViewEncouragement.text = "You did it!"
        } else {
            val encouragements = listOf("Way to go!", "You got this!", "Keep it up!", "Great job!")
            binding.textViewEncouragement.text = encouragements.random()
        }
        
        binding.btnContinueProgress.setOnClickListener {
            if (progressPercent >= 100) {
                // Mark chapter as completed in SharedPreferences
                val sharedPrefs = getSharedPreferences("SeikakuPrefs", Context.MODE_PRIVATE)
                sharedPrefs.edit().putBoolean("COMPLETED_$chapterTitle", true).apply()

                // Navigate to MainActivity when complete
                val intent = Intent(this, MainActivity::class.java)
                intent.flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                startActivity(intent)
                finish()
            } else {
                // Return result to SpeakingFunction to move to next word
                setResult(RESULT_OK)
                finish()
            }
        }
    }
}
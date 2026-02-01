package com.kagetraven.seikaku

import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.os.Bundle
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.widget.ImageButton
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.button.MaterialButton
import kotlin.math.abs

class MainActivity : AppCompatActivity() {

    private lateinit var gestureDetector: GestureDetector

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        // Back button to Startup screen
        findViewById<ImageButton>(R.id.btnBack).setOnClickListener {
            val intent = Intent(this, StartupActivity::class.java)
            startActivity(intent)
            finish()
        }

        // Profile button
        findViewById<ImageButton>(R.id.btnProfile).setOnClickListener {
            val intent = Intent(this, ProfileActivity::class.java)
            startActivity(intent)
        }

        // Setup individual chapters
        setupChapter(R.id.item_chapter1, "Chapter 1")
        setupChapter(R.id.item_chapter2, "Chapter 2")
        setupChapter(R.id.item_chapter3, "Chapter 3")
        setupChapter(R.id.item_chapter4, "Chapter 4")
        setupChapter(R.id.item_chapter5, "Chapter 5")
        setupChapter(R.id.item_chapter6, "Chapter 6")
        setupChapter(R.id.item_chapter7, "Chapter 7")
        setupChapter(R.id.item_chapter8, "Chapter 8")

        // Gesture detection for swiping to Leaderboard
        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(
                e1: MotionEvent?,
                e2: MotionEvent,
                velocityX: Float,
                velocityY: Float
            ): Boolean {
                if (e1 == null) return false
                val diffX = e2.x - e1.x
                val diffY = e2.y - e1.y
                if (abs(diffX) > abs(diffY)) {
                    if (abs(diffX) > 100 && abs(velocityX) > 100) {
                        if (diffX < 0) {
                            // Swipe Left -> Open Leaderboard
                            val intent = Intent(this@MainActivity, LeaderboardActivity::class.java)
                            startActivity(intent)
                            overridePendingTransition(R.anim.slide_in_right, R.anim.slide_out_left)
                            return true
                        }
                    }
                }
                return false
            }
        })

        findViewById<View>(R.id.main).setOnTouchListener { _, event ->
            gestureDetector.onTouchEvent(event)
        }
        
        // Also apply to scrollview so it doesn't swallow gestures
        findViewById<View>(R.id.scrollView).setOnTouchListener { _, event ->
            gestureDetector.onTouchEvent(event)
            false // return false so scrollview can still scroll
        }
    }

    override fun onResume() {
        super.onResume()
        // Refresh chapter states when returning to this screen
        setupChapter(R.id.item_chapter1, "Chapter 1")
        setupChapter(R.id.item_chapter2, "Chapter 2")
        setupChapter(R.id.item_chapter3, "Chapter 3")
        setupChapter(R.id.item_chapter4, "Chapter 4")
        setupChapter(R.id.item_chapter5, "Chapter 5")
        setupChapter(R.id.item_chapter6, "Chapter 6")
        setupChapter(R.id.item_chapter7, "Chapter 7")
        setupChapter(R.id.item_chapter8, "Chapter 8")
    }

    private fun setupChapter(chapterItemId: Int, title: String) {
        val chapterView = findViewById<View>(chapterItemId)
        val titleText = chapterView.findViewById<TextView>(R.id.textViewChapterNumber)
        val playButton = chapterView.findViewById<MaterialButton>(R.id.btnPlay)

        titleText.text = title
        
        val sharedPrefs = getSharedPreferences("SeikakuPrefs", Context.MODE_PRIVATE)
        val isCompleted = sharedPrefs.getBoolean("COMPLETED_$title", false)

        if (isCompleted) {
            playButton.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#56C439"))
            playButton.setIconResource(R.drawable.ic_check)
        } else {
            playButton.backgroundTintList = ColorStateList.valueOf(Color.parseColor("#FF5959"))
            playButton.setIconResource(R.drawable.ic_play_arrow)
        }
        
        if (title == "Chapter 1") {
            playButton.setOnClickListener {
                val intent = Intent(this, SpeakingFunction::class.java)
                intent.putExtra("CHAPTER_TITLE", title)
                startActivity(intent)
            }
            playButton.alpha = 1.0f
        } else {
            // Chapters 2-8 open the Premium screen
            playButton.setOnClickListener {
                val intent = Intent(this, PremiumActivity::class.java)
                startActivity(intent)
            }
            playButton.alpha = 0.7f // Slightly dimmed to suggest premium
        }
    }
}
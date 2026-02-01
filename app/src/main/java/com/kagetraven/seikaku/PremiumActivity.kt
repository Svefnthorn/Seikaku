package com.kagetraven.seikaku

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.kagetraven.seikaku.databinding.ActivityPremiumBinding

class PremiumActivity : AppCompatActivity() {

    private lateinit var binding: ActivityPremiumBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityPremiumBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnBack.setOnClickListener {
            finish()
        }

        binding.btnFreeTrial.setOnClickListener {
            // Logic for starting free trial
        }

        binding.btnSignIn.setOnClickListener {
            // Logic for signing in
        }
    }
}
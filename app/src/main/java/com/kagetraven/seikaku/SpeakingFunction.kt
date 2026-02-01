package com.kagetraven.seikaku

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.BitmapFactory
import android.graphics.Color
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaPlayer
import android.media.MediaRecorder
import android.media.ToneGenerator
import android.media.audiofx.NoiseSuppressor
import android.os.*
import android.util.Base64
import android.util.Log
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import com.kagetraven.seikaku.databinding.ActivitySpeakingFunctionBinding
import nl.dionsegijn.konfetti.core.Party
import nl.dionsegijn.konfetti.core.Position
import nl.dionsegijn.konfetti.core.emitter.Emitter
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import java.io.*
import java.util.concurrent.TimeUnit

data class JapaneseItem(val id: String, val text: String, val phonetic: String)

class SpeakingFunction : AppCompatActivity() {

    private lateinit var binding: ActivitySpeakingFunctionBinding
    private val client = OkHttpClient()
    private var mediaPlayer: MediaPlayer? = null

    // Audio recording properties
    private var audioRecord: AudioRecord? = null
    private var noiseSuppressor: NoiseSuppressor? = null
    private var recordingThread: Thread? = null
    private var isRecording = false

    private val sampleRate = 44100
    private val channelConfig = AudioFormat.CHANNEL_IN_MONO
    private val audioEncoding = AudioFormat.ENCODING_PCM_16BIT
    private val bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioEncoding)

    private var tempRawFile: File? = null
    private var finalWavFile: File? = null

    // Hardcoded words and sentences with IDs and Phonetics
    private val wordsList = listOf(
        JapaneseItem("BeMale", "です", "Desu"),
        JapaneseItem("IMale", "私 ", "Watashi"),
        JapaneseItem("HelloMale", "こんにちは", "Konnichiwa"),
        JapaneseItem("IAmAStudentMale", "私は学生です", "Watashi wa gakusei desu"),
        JapaneseItem("TeacherMale", "先生", "Sensei"),
        JapaneseItem("YesMale", "はい", "Hai"),
        JapaneseItem("YesIAmATeacherMale", "はい、私は先生です。", "Hai, watashi wa sensei desu")
    )
    private var currentWordIndex = 0

    private val requestRecordAudioPermission = 200
    private var permissionToRecordAccepted = false
    private val permissions: Array<String> = arrayOf(Manifest.permission.RECORD_AUDIO)

    private val progressLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == RESULT_OK) {
            // Move to the next word
            currentWordIndex = (currentWordIndex + 1) % wordsList.size
            updateDisplayedWord()
            resetUIForNewWord()
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        permissionToRecordAccepted = if (requestCode == requestRecordAudioPermission) {
            grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
        } else {
            false
        }
        if (!permissionToRecordAccepted) {
            Log.e("SpeakingFunction", "Permission to record audio was denied")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySpeakingFunctionBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ActivityCompat.requestPermissions(this, permissions, requestRecordAudioPermission)

        updateDisplayedWord()
        setupRecordButton()
        
        // Back button to previous word or finish activity
        binding.btnBack.setOnClickListener {
            if (currentWordIndex > 0) {
                currentWordIndex--
                updateDisplayedWord()
                resetUIForNewWord()
            } else {
                finish()
            }
        }
        
        // Continue button opens the progress tracking view
        binding.btnContinue.setOnClickListener {
            val intent = Intent(this, ProgressTrackingActivity::class.java)
            intent.putExtra("CURRENT", currentWordIndex + 1)
            intent.putExtra("TOTAL", wordsList.size)
            intent.putExtra("CHAPTER_TITLE", getIntent().getStringExtra("CHAPTER_TITLE") ?: "Chapter 1")
            progressLauncher.launch(intent)
        }

        // Play Example Audio Button
        binding.btnPlayExample.setOnClickListener {
            playExampleAudio()
        }
    }

    private fun playExampleAudio() {
        val currentItem = wordsList[currentWordIndex]
        val audioUrl = "https://jacinto-unsinuated-semiphenomenally.ngrok-free.dev/audio/${currentItem.id}.wav"
        
        try {
            mediaPlayer?.release()
            mediaPlayer = MediaPlayer().apply {
                setAudioAttributes(
                    AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .build()
                )
                setDataSource(audioUrl)
                prepareAsync()
                setOnPreparedListener { start() }
                setOnErrorListener { _, what, extra ->
                    Log.e("SpeakingFunction", "MediaPlayer error: what=$what, extra=$extra")
                    false
                }
            }
        } catch (e: Exception) {
            Log.e("SpeakingFunction", "Error playing example audio", e)
        }
    }

    private fun resetUIForNewWord() {
        // Clear previous results
        binding.cardViewGraph.visibility = View.GONE
        binding.imageViewGraph.setImageDrawable(null)
        binding.textViewResult.text = "Hold the button and say the word above."
    }

    private fun updateDisplayedWord() {
        val item = wordsList[currentWordIndex]
        binding.textViewWord.text = item.text
        binding.textViewPhonetic.text = item.phonetic
    }

    private fun setupRecordButton() {
        val redColor = Color.parseColor("#FF5959")
        val whiteColor = Color.WHITE

        binding.btnRecord.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    // Invert colors: Background white, Icon red
                    binding.btnRecord.backgroundTintList = ColorStateList.valueOf(whiteColor)
                    binding.btnRecord.iconTint = ColorStateList.valueOf(redColor)
                    startRecording()
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    // Restore colors: Background red, Icon white
                    binding.btnRecord.backgroundTintList = ColorStateList.valueOf(redColor)
                    binding.btnRecord.iconTint = ColorStateList.valueOf(whiteColor)
                    stopRecording()
                    uploadAudio()
                    true
                }
                else -> false
            }
        }
    }

    private fun startRecording() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            return
        }

        // Hide card when starting a new recording
        binding.cardViewGraph.visibility = View.GONE

        tempRawFile = File(externalCacheDir, "temp.raw")
        finalWavFile = File(externalCacheDir, "recording.wav")

        audioRecord = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            sampleRate,
            channelConfig,
            audioEncoding,
            bufferSize
        )

        // Enable Noise Suppression if available
        if (NoiseSuppressor.isAvailable()) {
            noiseSuppressor = NoiseSuppressor.create(audioRecord!!.audioSessionId)
            noiseSuppressor?.enabled = true
            Log.d("SpeakingFunction", "Noise suppressor enabled")
        } else {
            Log.d("SpeakingFunction", "Noise suppressor not available on this device")
        }

        audioRecord?.startRecording()
        isRecording = true

        recordingThread = Thread {
            writeAudioDataToFile()
        }
        recordingThread?.start()
    }

    private fun writeAudioDataToFile() {
        val data = ByteArray(bufferSize)
        var os: FileOutputStream? = null
        try {
            os = FileOutputStream(tempRawFile)
            while (isRecording) {
                val read = audioRecord?.read(data, 0, bufferSize) ?: 0
                if (read > 0) {
                    os.write(data, 0, read)
                }
            }
        } catch (e: IOException) {
            Log.e("SpeakingFunction", "Error writing raw file", e)
        } finally {
            try {
                os?.close()
            } catch (e: IOException) {
                Log.e("SpeakingFunction", "Error closing output stream", e)
            }
        }
    }

    private fun stopRecording() {
        isRecording = false
        
        noiseSuppressor?.apply {
            enabled = false
            release()
        }
        noiseSuppressor = null

        audioRecord?.apply {
            try {
                stop()
                release()
            } catch (e: Exception) {
                Log.e("SpeakingFunction", "Error stopping AudioRecord", e)
            }
        }
        audioRecord = null
        try {
            recordingThread?.join()
        } catch (e: InterruptedException) {
            Log.e("SpeakingFunction", "Recording thread interrupted", e)
        }
        
        convertRawToWav(tempRawFile, finalWavFile)
    }

    private fun convertRawToWav(rawFile: File?, wavFile: File?) {
        if (rawFile == null || wavFile == null || !rawFile.exists()) return

        val totalAudioLen = rawFile.length()
        val totalDataLen = totalAudioLen + 36
        val channels = 1
        val byteRate = 16 * sampleRate * channels / 8L

        val data = ByteArray(bufferSize)
        var inputStream: FileInputStream? = null
        var outputStream: FileOutputStream? = null

        try {
            inputStream = FileInputStream(rawFile)
            outputStream = FileOutputStream(wavFile)
            
            writeWavHeader(outputStream, totalAudioLen, totalDataLen, sampleRate.toLong(), channels, byteRate)
            
            var length: Int
            while (inputStream.read(data).also { length = it } != -1) {
                outputStream.write(data, 0, length)
            }
        } catch (e: IOException) {
            Log.e("SpeakingFunction", "Error converting to wav", e)
        } finally {
            try {
                inputStream?.close()
                outputStream?.close()
            } catch (e: IOException) {
                Log.e("SpeakingFunction", "Error closing streams", e)
            }
        }
    }

    private fun writeWavHeader(
        out: FileOutputStream,
        totalAudioLen: Long,
        totalDataLen: Long,
        longSampleRate: Long,
        channels: Int,
        byteRate: Long
    ) {
        val header = ByteArray(44)
        header[0] = 'R'.code.toByte()
        header[1] = 'I'.code.toByte()
        header[2] = 'F'.code.toByte()
        header[3] = 'F'.code.toByte()
        header[4] = (totalDataLen and 0xffL).toByte()
        header[5] = (totalDataLen shr 8 and 0xffL).toByte()
        header[6] = (totalDataLen shr 16 and 0xffL).toByte()
        header[7] = (totalDataLen shr 24 and 0xffL).toByte()
        header[8] = 'W'.code.toByte()
        header[9] = 'A'.code.toByte()
        header[10] = 'V'.code.toByte()
        header[11] = 'E'.code.toByte()
        header[12] = 'f'.code.toByte()
        header[13] = 'm'.code.toByte()
        header[14] = 't'.code.toByte()
        header[15] = ' '.code.toByte()
        header[16] = 16
        header[17] = 0
        header[18] = 0
        header[19] = 0
        header[20] = 1
        header[21] = 0
        header[22] = channels.toByte()
        header[23] = 0
        header[24] = (longSampleRate and 0xffL).toByte()
        header[25] = (longSampleRate shr 8 and 0xffL).toByte()
        header[26] = (longSampleRate shr 16 and 0xffL).toByte()
        header[27] = (longSampleRate shr 24 and 0xffL).toByte()
        header[28] = (byteRate and 0xffL).toByte()
        header[29] = (byteRate shr 8 and 0xffL).toByte()
        header[30] = (byteRate shr 16 and 0xffL).toByte()
        header[31] = (byteRate shr 24 and 0xffL).toByte()
        header[32] = (channels * 16 / 8).toByte()
        header[33] = 0
        header[34] = 16
        header[35] = 0
        header[36] = 'd'.code.toByte()
        header[37] = 'a'.code.toByte()
        header[38] = 't'.code.toByte()
        header[39] = 'a'.code.toByte()
        header[40] = (totalAudioLen and 0xffL).toByte()
        header[41] = (totalAudioLen shr 8 and 0xffL).toByte()
        header[42] = (totalAudioLen shr 16 and 0xffL).toByte()
        header[43] = (totalAudioLen shr 24 and 0xffL).toByte()
        out.write(header, 0, 44)
    }

    private fun uploadAudio() {
        val file = finalWavFile ?: return
        if (!file.exists()) return

        val currentItem = wordsList[currentWordIndex]
        binding.textViewResult.text = "Uploading and processing..."

        val requestBody = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", file.name, file.asRequestBody("audio/wav".toMediaTypeOrNull()))
            .addFormDataPart("word_id", currentItem.id)
            .addFormDataPart("word_text", currentItem.text)
            .build()

        val request = Request.Builder()
            .url("https://jacinto-unsinuated-semiphenomenally.ngrok-free.dev/analyze")
            .post(requestBody)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                runOnUiThread {
                    binding.textViewResult.text = "Error: ${e.message}"
                }
            }

            override fun onResponse(call: Call, response: Response) {
                response.use { resp ->
                    if (!resp.isSuccessful) {
                        runOnUiThread {
                            binding.textViewResult.text = "Server Error: ${resp.code}"
                        }
                        return
                    }

                    val responseData = resp.body?.string()
                    if (responseData != null) {
                        try {
                            val json = JSONObject(responseData)
                            val result = json.optString("feedback", "Processed successfully")
                            val scoreStr = json.optString("score", "0")
                            val imageBase64 = json.optString("graph_image", "")

                            // Extract numerical score for logic
                            val score = scoreStr.filter { it.isDigit() }.toIntOrNull() ?: 0

                            val bitmap = if (imageBase64.isNotEmpty()) {
                                try {
                                    val decodedString = Base64.decode(imageBase64, Base64.DEFAULT)
                                    BitmapFactory.decodeByteArray(decodedString, 0, decodedString.size)
                                } catch (e: Exception) {
                                    Log.e("SpeakingFunction", "Error decoding image", e)
                                    null
                                }
                            } else null
                            
                            runOnUiThread {
                                binding.textViewResult.text = "Result: $result\nScore: $scoreStr"
                                if (bitmap != null) {
                                    binding.imageViewGraph.setImageBitmap(bitmap)
                                    binding.cardViewGraph.visibility = View.VISIBLE
                                } else {
                                    binding.imageViewGraph.setImageDrawable(null)
                                    binding.cardViewGraph.visibility = View.GONE
                                }

                                // Reward/Feedback logic based on score
                                handleScoreFeedback(score)
                            }
                        } catch (e: Exception) {
                            runOnUiThread {
                                binding.textViewResult.text = "Failed to parse response"
                            }
                        }
                    } else {
                        runOnUiThread {
                            binding.textViewResult.text = "Empty response from server"
                        }
                    }
                }
            }
        })
    }

    private fun handleScoreFeedback(score: Int) {
        if (score > 70) {
            // Play light chime for scores above 70
            playChime()
            
            if (score >= 90) {
                // Pop confetti for high scores
                showConfetti()
            }
        } else {
            // Double haptic buzz for score 70 or lower
            vibrateDoubleBuzz()
        }
    }

    private fun playChime() {
        try {
            val toneGen = ToneGenerator(AudioManager.STREAM_MUSIC, 100)
            toneGen.startTone(ToneGenerator.TONE_PROP_BEEP, 150)
        } catch (e: Exception) {
            Log.e("SpeakingFunction", "Error playing chime", e)
        }
    }

    private fun showConfetti() {
        val party = Party(
            speed = 0f,
            maxSpeed = 30f,
            damping = 0.9f,
            spread = 360,
            colors = listOf(0xfce18a, 0xff726d, 0xf4306d, 0xb48def),
            position = Position.Relative(0.5, 0.3),
            emitter = Emitter(duration = 100, TimeUnit.MILLISECONDS).max(100)
        )
        binding.konfettiView.start(party)
    }

    private fun vibrateDoubleBuzz() {
        // 1. Use View Haptic Feedback as a highly reliable fallback
        binding.root.isHapticFeedbackEnabled = true
        binding.root.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)

        // 2. Use System Vibrator Service with AudioAttributes
        try {
            @Suppress("DEPRECATION")
            val vibrator = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            
            if (vibrator.hasVibrator()) {
                val audioAttributes = AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
                    .build()

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    // Two distinct pulses: 150ms on, 100ms off, 150ms on
                    val timings = longArrayOf(0, 150, 100, 150)
                    val amplitudes = intArrayOf(0, 255, 0, 255)
                    val effect = VibrationEffect.createWaveform(timings, amplitudes, -1)
                    vibrator.vibrate(effect, audioAttributes)
                } else {
                    // Legacy vibration
                    @Suppress("DEPRECATION")
                    vibrator.vibrate(longArrayOf(0, 150, 100, 150), -1)
                }
            }
        } catch (e: Exception) {
            Log.e("SpeakingFunction", "Error during vibration", e)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        mediaPlayer?.release()
        mediaPlayer = null
    }
}
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import io
import base64
import numpy as np
import librosa
import whisper
from fastdtw import fastdtw
from scipy.signal import savgol_filter
from difflib import SequenceMatcher
from contextlib import asynccontextmanager
import matplotlib
import time
from fastapi.responses import FileResponse
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import json
import os
from datetime import datetime, timedelta

PROGRESS_FILE = "user_progress.json"

# Default state
user_data = {
    "current_streak": 0,
    "last_practice_date": None,
    "total_sessions": 0,
    "best_streak": 0,
    "scores_history": []
}

def load_progress():
    global user_data
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            user_data = json.load(f)
    else:
        # 🛠️ DEFAULT DEMO PROFILE
        # This makes the app look "alive" the moment you turn it on
        user_data = {
            "current_streak": 4,
            "last_practice_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "total_sessions": 12,
            "best_streak": 7,
            "scores_history": [82, 88, 91, 85, 89] # Believable historical scores
        }
        save_progress()

def save_progress():
    with open(PROGRESS_FILE, "w") as f:
        json.dump(user_data, f, indent=4)

# Load immediately on startup
load_progress()


app = FastAPI()

# --- CONFIG ---
REF_DIR = "references"
REF_CACHE = {}
whisper_model = None


# --- LIFESPAN STARTUP ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Load Reference Audio
    if not os.path.exists(REF_DIR):
        os.makedirs(REF_DIR)
    else:
        for filename in os.listdir(REF_DIR):
            if filename.endswith(".wav") or filename.endswith(".mp3"):
                word_id = os.path.splitext(filename)[0]
                path = os.path.join(REF_DIR, filename)
                try:
                    norm_pitch = process_audio_file(path)
                    REF_CACHE[word_id] = {"norm_pitch": norm_pitch}
                    print(f"✅ Loaded Reference: {word_id}")
                except Exception as e:
                    print(f"❌ Failed to load {filename}: {e}")

    # 2. Load Whisper
    print("🎧 Loading Whisper Model (Small)...")
    global whisper_model
    whisper_model = whisper.load_model("small")
    print("✅ Whisper Ready.")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MAPS ---
SYLLABLE_MAP = {
    "HelloMale": ["Ko", "n", "Ni", "Chi", "Wa"],
    "HelloFemale": ["Ko", "n", "Ni", "Chi", "Wa"],
    "YesMale": ["Ha", "i"],
    "YesFemale": ["Ha", "i"],
    "IMale": ["Wa", "Ta", "Shi"],
    "IFemale": ["Wa", "Ta", "Shi"],
    "BeMale": ["De", "Su"],
    "BeFemale": ["De", "Su"],
    "TeacherMale": ["Se", "n", "Se", "i"],
    "TeacherFemale": ["Se", "n", "Se", "i"],
    "YesIAmATeacherMale": ["Ha", "i", "Wa", "Ta", "Shi", "Wa", "Se", "n", "Se", "i", "De", "Su"],
    "YesIAmATeacherFemale": ["Ha", "i", "Wa", "Ta", "Shi", "Wa", "Se", "n", "Se", "i", "De", "Su"],
    "IAmAStudentMale": ["Wa", "Ta", "Shi", "Wa", "Ga", "Ku", "Se", "i", "De", "Su"],
    "IAmAStudentFemale": ["Wa", "Ta", "Shi", "Wa", "Ga", "Ku", "Se", "i", "De", "Su"]
}

EXPECTED_TEXT_MAP = {
    "HelloMale": ["konnichiwa", "hello", "こんにちは", "こんにちわ"],
    "HelloFemale": ["konnichiwa", "hello", "こんにちは", "こんにちわ"],
    "YesMale": ["hai", "hi", "yes", "はい"],
    "YesFemale": ["hai", "hi", "yes", "はい"],
    "IMale": ["watashi", "watashiwa", "私", "わたし"],
    "IFemale": ["watashi", "watashiwa", "私", "わたし"],
    "BeMale": ["desu", "dess", "です"],
    "BeFemale": ["desu", "dess", "です"],
    "TeacherMale": ["sensei", "sensay", "先生", "せんせい"],
    "TeacherFemale": ["sensei", "sensay", "先生", "せんせい"],
    "YesIAmATeacherMale": ["hai watashi wa sensei desu", "i am a teacher", "はい私は先生です",
                           "はいわたしはせんせいです", "はい、私は先生です"],
    "YesIAmATeacherFemale": ["hai watashi wa sensei desu", "はい私は先生です", "はいわたしはせんせいです",
                             "はい、私は先生です"],
    "IAmAStudentMale": ["watashi wa gakusei desu", "i am a student", "私は学生です", "わたしはがくせいです"],
    "IAmAStudentFemale": ["watashi wa gakusei desu", "私は学生です", "わたしはがくせいです"]
}

# --- HELPERS ---
def check_for_silence(file_path):
    """Returns True if the audio is basically silent."""
    try:
        y, sr = librosa.load(file_path, sr=16000, mono=True)
        rms = librosa.feature.rms(y=y)
        if rms.mean() < 0.005:
            return True
        return False
    except:
        return True


def process_audio_file(file_path):
    try:
        y, sr = librosa.load(file_path, sr=22050, mono=True)
        y_trimmed, _ = librosa.effects.trim(y, top_db=25)
        f0, _, _ = librosa.pyin(y_trimmed, fmin=50, fmax=400, sr=sr)
        f0 = np.nan_to_num(f0)
        valid_pitch = f0[f0 > 0]
        if len(valid_pitch) == 0: return np.zeros(100)
        mean = np.mean(valid_pitch)
        std = np.std(valid_pitch)
        norm_pitch = (f0 - mean) / (std + 1e-6)
        norm_pitch[f0 < 1] = 0
        try:
            norm_pitch = savgol_filter(norm_pitch, 21, 2)
        except:
            pass
        return norm_pitch
    except:
        return np.zeros(100)


def validate_speech_content(audio_path, word_id):
    if whisper_model is None: return True, ""

    result = whisper_model.transcribe(
        audio_path,
        language="ja",
        fp16=False,
        initial_prompt="これは日本語の授業です。",

        # --- ANTI-LOOP & SPEED SETTINGS ---
        temperature=0.0,
        beam_size=1,
        best_of=1,
        compression_ratio_threshold=1.8,
        no_speech_threshold=0.6,
        condition_on_previous_text=False,
        logprob_threshold=-1.0
    )

    text = result["text"].lower().strip()

    # --- MANUAL REPETITION CLEANER ---
    #please just stop looping
    if len(text) > 50:
        text = text[:20]
        print(f"⚠️ Truncated repetition loop: {text}...")

    text = text.replace("。", "").replace("、", "").replace("!", "").replace("?", "")

    if word_id not in EXPECTED_TEXT_MAP: return True, text

    allowed = EXPECTED_TEXT_MAP[word_id]

    # Exact Match
    for phrase in allowed:
        if phrase in text: return True, text

    # Fuzzy Match
    best_ratio = 0.0
    for phrase in allowed:
        ratio = SequenceMatcher(None, phrase, text).ratio()
        if ratio > best_ratio: best_ratio = ratio

    if best_ratio > 0.6:
        return True, text

    return False, text

def get_syllable_regions(path, word_id):
    if word_id not in SYLLABLE_MAP: return []
    labels = SYLLABLE_MAP[word_id]
    if len(path) == 0: return []
    chunk_size = path[-1][0] / len(labels)
    regions = []
    last_idx = 0
    for i, label in enumerate(labels):
        target = int((i + 1) * chunk_size)
        curr_idx = len(path) - 1
        for k, (ref_idx, _) in enumerate(path):
            if ref_idx >= target:
                curr_idx = k
                break
        regions.append({"label": label, "start_index": last_idx, "end_index": curr_idx})
        last_idx = curr_idx
    return regions


def generate_graph(ref, user, regions, word_id):
    plt.figure(figsize=(10, 5))
    colors = ['#e6f2ff', '#fff0e6', '#e6ffe6']
    for i, r in enumerate(regions):
        plt.axvspan(r['start_index'], r['end_index'], color=colors[i % 3], alpha=0.5)
        plt.text((r['start_index'] + r['end_index']) / 2, 2.2, r['label'], ha='center', weight='bold')
    plt.plot(ref, 'g', linewidth=3, label='Teacher')
    plt.plot(user, 'r--', linewidth=3, label='You')
    plt.ylim(-3, 3)
    plt.legend()
    plt.title(f"Pronunciation: {word_id}")
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# --- ENDPOINTS ---
@app.get("/")
async def home():
    return {"message": "Server is Online! Send POST requests to /analyze"}


@app.get("/admin/reset-to-demo")
async def reset_to_demo():
    global user_data
    # 1. Revert to 4-day demo baseline
    user_data = {
        "current_streak": 4,
        "last_practice_date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "total_sessions": 12,
        "best_streak": 7,
        "scores_history": [82, 88, 91, 85, 89]
    }
    save_progress()

    # 2. Calculate average for the report
    avg = sum(user_data["scores_history"]) / len(user_data["scores_history"])

    # 3. Big terminal print for peace of mind
    print("\n" + "=" * 40)
    print("🟢 SYSTEM READY FOR JUDGE")
    print(f"📊 Starting Streak: {user_data['current_streak']}")
    print(f"📈 Starting Average: {avg}%")
    print(f"📅 Last Practice: {user_data['last_practice_date']} (Yesterday)")
    print("=" * 40 + "\n")

    return {"status": "success", "ready": True}

@app.get("/admin/prepare-demo-streak/{target_streak}")
async def prepare_demo(target_streak: int):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    user_data["current_streak"] = target_streak - 1
    user_data["last_practice_date"] = yesterday
    save_progress()

    #Set the streak to x and time to yesterday, so the next correct word will increase the streak
    return {"message": f"The next successful word will trigger streak {target_streak}."}


@app.get("/audio/{word_id}")
async def get_audio_file(word_id: str):
    file_path = f"references/{word_id}"

    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/wav")

    print(f"❌ Audio Load Fail: Server searched for '{file_path}'")
    return {"error": f"File '{word_id}.wav' not found in references folder."}

@app.get("/leaderboard")
async def get_leaderboard():
    # Calculate your real average
    history = user_data.get("scores_history", [])
    user_avg = sum(history) / len(history) if history else 0

    # Combined list: Real data + "NPC" competitors
    all_users = [
        {"name": "Sensei_Bot", "streak": 486, "avg_score": 99},
        {"name": "You (Hacker)", "streak": user_data["current_streak"], "avg_score": round(user_avg, 1)},
        {"name": "Kenji", "streak": 12, "avg_score": 78},
        {"name": "Yuki", "streak": 8, "avg_score": 89}
    ]

    # Sort by average score (highest first)
    return sorted(all_users, key=lambda x: x['avg_score'], reverse=True)


@app.get("/user/stats")
async def get_user_stats():
    # Calculate average on the fly so it's always accurate
    history = user_data.get("scores_history", [])
    avg = round(sum(history) / len(history), 1) if history else 0

    return {
        "current_streak": user_data["current_streak"],
        "best_streak": user_data["best_streak"],
        "total_sessions": user_data["total_sessions"],
        "user_average": avg,
        "history": history[-10:]  # Send the last 10 scores for a small chart
    }

@app.post("/analyze")
async def analyze_pitch(
        word_id: str = Form(...),
        file: UploadFile = File(...)
):
    start_time = time.time()
    temp_filename = f"temp_{file.filename}"

    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 1. VALIDATE SPEECH CONTENT (Whisper)
        is_text_correct, heard_text = validate_speech_content(temp_filename, word_id)

        # 2. CHECK REFERENCE CACHE
        if word_id not in REF_CACHE:
            return {"error": f"Reference audio for '{word_id}' not found."}

        # 3. EXTRACT PITCH & ALIGN (DTW)
        ref_norm = REF_CACHE[word_id]["norm_pitch"]
        user_norm = process_audio_file(temp_filename)
        dist, path = fastdtw(ref_norm, user_norm, dist=lambda x, y: abs(x - y))

        # 4. CALCULATE SCORE
        raw_score = max(0, 100 - (dist / len(path) * 25))
        final_score = int(raw_score)

        feedback_msg = "Great pronunciation!"
        if not is_text_correct:
            final_score = max(0, final_score - 50)
            feedback_msg = f"Heard '{heard_text}'. Accuracy affected by pronunciation."

        # 5. GENERATE VISUAL FEEDBACK
        ref_aligned = [ref_norm[i] for i, j in path]
        user_aligned = [user_norm[j] for i, j in path]
        regions = get_syllable_regions(path, word_id)
        graph = generate_graph(ref_aligned, user_aligned, regions, word_id)

        # 6. UPDATE GLOBAL STATS & PERSISTENCE
        user_data["scores_history"].append(final_score)
        if len(user_data["scores_history"]) > 50:
            user_data["scores_history"].pop(0)

        # Only award streak progress for successful attempts
        if is_text_correct and final_score > 70:
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)

            last_date_str = user_data.get("last_practice_date")
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date() if last_date_str else None

            if last_date == yesterday:
                user_data["current_streak"] += 1
            elif last_date != today:
                # If they missed a day, reset. If they already practiced today, do nothing.
                user_data["current_streak"] = 1

            user_data["last_practice_date"] = today.strftime("%Y-%m-%d")
            user_data["total_sessions"] += 1
            user_data["best_streak"] = max(user_data["best_streak"], user_data["current_streak"])
            save_progress()

        duration = round(time.time() - start_time, 2)
        print(f"⏱️ RESPONSE: {duration}s | Score: {final_score} | Streak: {user_data['current_streak']}")

        return {
            "score": final_score,
            "feedback": feedback_msg,
            "graph_image": graph,
            "processing_time": f"{duration}s",
            "current_streak": user_data["current_streak"],
            "user_average": round(sum(user_data["scores_history"]) / len(user_data["scores_history"]), 1)
        }

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"error": "Processing failed. Check audio quality."}

    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
if __name__ == "__main__":
    import uvicorn

uvicorn.run(app, host="0.0.0.0", port=8000)

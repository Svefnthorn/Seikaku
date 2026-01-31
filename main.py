from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import io
import base64
import numpy as np
import librosa
from fastdtw import fastdtw
from scipy.signal import savgol_filter
import matplotlib

matplotlib.use('Agg')  # <--- Critical: Headless Mode (No Popups)
import matplotlib.pyplot as plt

app = FastAPI()

# 1. SETUP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

REF_DIR = "references"
REF_CACHE = {}

# 2. THE MAP (Your Exact Version)
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


# 3. STARTUP: Load References
@app.on_event("startup")
async def load_references():
    if not os.path.exists(REF_DIR):
        os.makedirs(REF_DIR)
        return

    for filename in os.listdir(REF_DIR):
        if filename.endswith(".wav") or filename.endswith(".mp3"):
            word_id = os.path.splitext(filename)[0]
            path = os.path.join(REF_DIR, filename)
            try:
                # Pre-calculate the Teacher's Curve
                norm_pitch = process_audio_file(path)
                REF_CACHE[word_id] = {"norm_pitch": norm_pitch}
                print(f"Loaded: {word_id}")
            except Exception as e:
                print(f"Failed {filename}: {e}")


# 4. HELPER FUNCTIONS
def process_audio_file(file_path):
    try:
        y, sr = librosa.load(file_path, sr=22050, mono=True)
        y_trimmed, _ = librosa.effects.trim(y, top_db=20)
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


def get_syllable_regions_automatic(path, word_id):
    if word_id not in SYLLABLE_MAP: return []  # Safety check

    labels = SYLLABLE_MAP[word_id]
    num_syllables = len(labels)
    total_ref_frames = path[-1][0]
    chunk_size = total_ref_frames / num_syllables

    regions = []
    last_path_idx = 0

    for i, label in enumerate(labels):
        target_ref_frame = int((i + 1) * chunk_size)
        current_path_idx = len(path) - 1
        for k, (ref_idx, user_idx) in enumerate(path):
            if ref_idx >= target_ref_frame:
                current_path_idx = k
                break

        regions.append({
            "label": label,
            "start_index": last_path_idx,
            "end_index": current_path_idx
        })
        last_path_idx = current_path_idx
    return regions


def generate_smart_feedback(ref_aligned, user_aligned, regions):
    feedback_items = []
    for region in regions:
        start = region['start_index']
        end = region['end_index']
        if end - start < 5: continue

        r_slice = ref_aligned[start:end]
        u_slice = user_aligned[start:end]
        if len(r_slice) == 0: continue

        if np.mean(u_slice) > np.mean(r_slice) + 0.6:
            feedback_items.append(f"'{region['label']}' too high.")
        elif np.mean(u_slice) < np.mean(r_slice) - 0.6:
            feedback_items.append(f"'{region['label']}' too low.")

    return " ".join(feedback_items) if feedback_items else "Perfect pitch!"


def generate_graph_image(ref_aligned, user_aligned, regions, word_id):
    plt.figure(figsize=(10, 5))
    colors = ['#e6f2ff', '#fff0e6', '#e6ffe6']

    for i, region in enumerate(regions):
        start = region['start_index']
        end = region['end_index']
        plt.axvspan(start, end, color=colors[i % 3], alpha=0.5)
        mid_x = (start + end) / 2
        plt.text(mid_x, 2.2, region['label'], fontsize=12, ha='center', weight='bold')

    plt.plot(ref_aligned, color='green', label='Teacher', linewidth=3)
    plt.plot(user_aligned, color='red', label='You', linestyle='--', linewidth=3)

    plt.ylim(-3, 3)
    plt.legend(loc='lower right')
    plt.title(f"Pronunciation: {word_id}")
    plt.grid(True, alpha=0.3)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# 5. THE ENDPOINT (The Receiver)
@app.post("/analyze")
async def analyze_pitch(word_id: str, file: UploadFile = File(...)):
    # A. Save User Audio
    temp_filename = f"temp_{file.filename}"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # B. Check Reference
    if word_id not in REF_CACHE:
        if os.path.exists(temp_filename): os.remove(temp_filename)
        return {"error": f"Word '{word_id}' not found"}

    ref_norm = REF_CACHE[word_id]["norm_pitch"]

    # C. Process User Audio
    user_norm = process_audio_file(temp_filename)

    # D. Compare (DTW)
    dist, path = fastdtw(ref_norm, user_norm, dist=lambda x, y: abs(x - y))

    # E. Generate Results (Using DYNAMIC word_id)
    ref_aligned = [ref_norm[i] for i, j in path]
    user_aligned = [user_norm[j] for i, j in path]

    regions = get_syllable_regions_automatic(path, word_id)  # <--- Uses the variable from the App
    feedback = generate_smart_feedback(ref_aligned, user_aligned, regions)
    graph_b64 = generate_graph_image(ref_aligned, user_aligned, regions, word_id)

    avg_error = dist / len(path)
    score = max(0, 100 - (avg_error * 25))

    # F. Cleanup
    if os.path.exists(temp_filename):
        os.remove(temp_filename)

    return {
        "score": int(score),
        "feedback": feedback,
        "graph_image": graph_b64
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
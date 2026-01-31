import librosa
import matplotlib

matplotlib.use('Agg')  # <--- Keeps it headless
import matplotlib.pyplot as plt
import io
import base64
import numpy as np
from fastdtw import fastdtw
from scipy.signal import savgol_filter

# --- 1. CONFIG ---
SYLLABLE_MAP = {
    # --- HELLO (Konnichiwa) ---
    "HelloMale":   ["Ko", "n", "Ni", "Chi", "Wa"],
    "HelloFemale": ["Ko", "n", "Ni", "Chi", "Wa"],

    # --- YES (Hai) ---
    "YesMale":   ["Ha", "i"],
    "YesFemale": ["Ha", "i"],

    # --- I / ME (Watashi) ---
    "IMale":   ["Wa", "Ta", "Shi"],
    "IFemale": ["Wa", "Ta", "Shi"],

    # --- TO BE (Desu) ---
    "BeMale":   ["De", "Su"],
    "BeFemale": ["De", "Su"],

    # --- TEACHER (Sensei) ---
    "TeacherMale":   ["Se", "n", "Se", "i"],
    "TeacherFemale": ["Se", "n", "Se", "i"],

    # --- SENTENCE 1: "Yes, I am a teacher" ---
    # Hai, watashi wa sensei desu
    "YesIAmATeacherMale": [
        "Ha", "i", "Wa", "Ta", "Shi", "Wa", "Se", "n", "Se", "i", "De", "Su"
    ],
    "YesIAmATeacherFemale": [
        "Ha", "i", "Wa", "Ta", "Shi", "Wa", "Se", "n", "Se", "i", "De", "Su"
    ],

    # --- SENTENCE 2: "I am a student" ---
    # Watashi wa gakusei desu
    "IAmAStudentMale": [
        "Wa", "Ta", "Shi", "Wa", "Ga", "Ku", "Se", "i", "De", "Su"
    ],
    "IAmAStudentFemale": [
        "Wa", "Ta", "Shi", "Wa", "Ga", "Ku", "Se", "i", "De", "Su"
    ]
}
# --- 2. HELPER FUNCTIONS ---
def get_syllable_regions_automatic(path, word_id):
    if word_id not in SYLLABLE_MAP:
        return []

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


def extract_pitch(audio_path):
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    y_trimmed, _ = librosa.effects.trim(y, top_db=20)
    f0, _, _ = librosa.pyin(y_trimmed, fmin=50, fmax=400, sr=sr)
    f0 = np.nan_to_num(f0)

    valid_pitch = f0[f0 > 0]
    if len(valid_pitch) == 0:
        return np.zeros(100)

    mean = np.mean(valid_pitch)
    std = np.std(valid_pitch)
    norm_pitch = (f0 - mean) / (std + 1e-6)

    # Silence Clamp & Smoothing
    norm_pitch[f0 < 1] = 0
    # Try/Except for savgol in case array is too short
    try:
        norm_pitch = savgol_filter(norm_pitch, 21, 2)
    except:
        pass

    return norm_pitch


def generate_smart_feedback(ref_aligned, user_aligned, regions):
    feedback_items = []

    for region in regions:
        # FIX: Changed start_x -> start_index
        start = region['start_index']
        end = region['end_index']

        if end - start < 5: continue

        r_slice = ref_aligned[start:end]
        u_slice = user_aligned[start:end]

        if len(r_slice) == 0: continue

        r_avg = np.mean(r_slice)
        u_avg = np.mean(u_slice)

        if u_avg > r_avg + 0.6:
            feedback_items.append(f"'{region['label']}' too high.")
        elif u_avg < r_avg - 0.6:
            feedback_items.append(f"'{region['label']}' too low.")

    if not feedback_items:
        return "Perfect pitch!"

    return " ".join(feedback_items)


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


# --- 3. MAIN TEST FUNCTION ---
def compare_audio(teacher_file, student_file):
    print(f"--- Comparing {teacher_file} vs {student_file} ---")

    ref_norm = extract_pitch(teacher_file)
    user_norm = extract_pitch(student_file)

    distance, path = fastdtw(ref_norm, user_norm, dist=lambda x, y: abs(x - y))

    # Prepare data for generation
    ref_aligned = [ref_norm[i] for i, j in path]
    user_aligned = [user_norm[j] for i, j in path]

    # Use "IMale" or "watashi" to match the SYLLABLE_MAP keys
    word_id = "IMale"
    regions = get_syllable_regions_automatic(path, word_id)

    # Generate the goods
    feedback = generate_smart_feedback(ref_aligned, user_aligned, regions)
    image_b64 = generate_graph_image(ref_aligned, user_aligned, regions, word_id)

    avg_error = distance / len(path)
    score = max(0, 100 - (avg_error * 25))

    print(f"Final Score: {int(score)}/100")
    print(f"Feedback: {feedback}")
    print(f"Image String (First 50 chars): {image_b64[:50]}...")
    print("✅ TEST SUCCESSFUL")


if __name__ == "__main__":
    compare_audio("references/IMale.wav", "test_input.wav")
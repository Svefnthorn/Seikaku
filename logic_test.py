import librosa
import numpy as np
import matplotlib.pyplot as plt
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean


def extract_pitch(audio_path):
    """
    Loads audio, trims silence, and extracts the pitch curve (f0).
    Returns: Normalized Pitch Array (Z-Score)
    """
    # 1. Load Audio
    # sr=22050 is standard. Mono=True mixes stereo to mono.
    y, sr = librosa.load(audio_path, sr=22050, mono=True)

    # 2. Trim Silence (CRITICAL STEP)
    # top_db=20 means "cut anything 20dB quieter than the peak"
    y_trimmed, _ = librosa.effects.trim(y, top_db=20)

    # 3. Extract Pitch (Probabilistic YIN)
    # fmin=50Hz (Deep male), fmax=400Hz (High female)
    f0, voiced_flag, _ = librosa.pyin(y_trimmed, fmin=50, fmax=400, sr=sr)

    # 4. Handle "Unvoiced" parts (Silence/Breaths) within the word
    # Replace NaNs with 0
    f0 = np.nan_to_num(f0)

    # 5. Z-Score Normalization
    # We only calculate Mean/Std on the ACTUAL voice (f0 > 0)
    # This prevents silence from dragging down the average.
    valid_pitch = f0[f0 > 0]

    if len(valid_pitch) == 0:
        print(f"Warning: No voice detected in {audio_path}")
        return np.zeros(100)  # Return empty line

    mean = np.mean(valid_pitch)
    std = np.std(valid_pitch)

    # Apply formula: (x - mean) / std
    # We add 1e-6 to std to prevent division by zero
    norm_pitch = (f0 - mean) / (std + 1e-6)

    # Clean up: Force silence back to a specific "floor" value or 0 for the math
    # Here we keep it as is, because DTW handles shape well.
    return norm_pitch


def compare_audio(teacher_file, student_file):
    print(f"--- Comparing {teacher_file} vs {student_file} ---")

    # 1. Process both files
    ref_norm = extract_pitch(teacher_file)
    user_norm = extract_pitch(student_file)

    # 2. Dynamic Time Warping (DTW)
    # This aligns the user's speed to the teacher's speed.
    # 'dist' is the total cumulative distance (error).
    # 'path' is the list of coordinate pairs [(x1, y1), (x2, y2)...]
    distance, path = fastdtw(ref_norm, user_norm, dist=euclidean)

    # 3. Calculate Score
    # Distance is "Total Error". We need "Average Error per Frame".
    avg_error = distance / len(path)

    # Heuristic: If average error is > 1.5, it's a fail.
    # Score = 100 - (Error * ScalingFactor)
    score = max(0, 100 - (avg_error * 50))

    print(f"Total DTW Distance: {distance:.2f}")
    print(f"Average Error: {avg_error:.2f}")
    print(f"FINAL SCORE: {int(score)}/100")

    # 4. Visualize the Alignment
    visualize_comparison(ref_norm, user_norm, path)


def visualize_comparison(ref, user, path):
    """
    Plots the two signals aligned to show the match.
    """
    # Create aligned arrays based on the DTW path
    ref_aligned = []
    user_aligned = []

    for r_idx, u_idx in path:
        ref_aligned.append(ref[r_idx])
        user_aligned.append(user[u_idx])

    plt.figure(figsize=(10, 5))
    plt.plot(ref_aligned, color='green', label='Teacher (Reference)', linewidth=2)
    plt.plot(user_aligned, color='red', label='Student (You)', linestyle='--', linewidth=2)
    plt.title("Pitch Accent Alignment")
    plt.legend()
    plt.grid(True)
    plt.show()


# --- RUN IT ---
# Replace these with your actual filenames
if __name__ == "__main__":
    # Create dummy files if you don't have them yet to test logic
    # compare_audio("references/hashi.wav", "my_recording.wav")
    pass
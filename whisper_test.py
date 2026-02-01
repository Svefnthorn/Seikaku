import whisper
from difflib import SequenceMatcher
import os

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

    "YesIAmATeacherMale": [
        "hai watashi wa sensei desu",
        "i am a teacher",
        "はい私は先生です",
        "はいわたしはせんせいです",
        "はい、私は先生です"
    ],
    "YesIAmATeacherFemale": [
        "hai watashi wa sensei desu",
        "はい私は先生です",
        "はいわたしはせんせいです",
        "はい、私は先生です"
    ],

    "IAmAStudentMale": [
        "watashi wa gakusei desu",
        "i am a student",
        "私は学生です",
        "わたしはがくせいです"
    ],
    "IAmAStudentFemale": [
        "watashi wa gakusei desu",
        "私は学生です",
        "わたしはがくせいです"
    ]
}


def validate_speech_content(audio_path, word_id):
    print(f"🎧 Loading Whisper Model (Tiny)...")
    # Load model (this downloads ~70MB the first time)
    model = whisper.load_model("tiny")

    print(f"🎤 Transcribing '{audio_path}'...")
    # 1. Transcribe (Force Japanese for better accuracy)
    result = model.transcribe(audio_path, language="ja")
    text = result["text"].lower().strip()

    # Clean punctuation
    text = text.replace("。", "").replace("、", "").replace("!", "").replace("?", "")
    print(f"📝 I Heard: '{text}'")

    # 2. Validation Logic
    if word_id not in EXPECTED_TEXT_MAP:
        print("⚠️ No expected text map found for this ID. Skipping validation.")
        return True

    allowed_phrases = EXPECTED_TEXT_MAP[word_id]
    print(f"✅ Expected: {allowed_phrases}")

    # Check for exact or fuzzy match
    matched = False
    for phrase in allowed_phrases:
        # Check 1: Is the phrase inside the text?
        if phrase in text:
            matched = True
            break

        # Check 2: Fuzzy match (80% similarity)
        similarity = SequenceMatcher(None, phrase, text).ratio()
        if similarity > 0.8:
            matched = True
            break

    if matched:
        print("🎉 MATCH! The word is correct.")
        return True
    else:
        print("❌ FAIL. Text did not match.")
        return False


# --- RUN THE TEST ---
if __name__ == "__main__":
    # We test using one of your existing reference files
    test_file = "test_input.wav"
    test_id = "IMale"

    # Check if file exists first
    if os.path.exists(test_file):
        validate_speech_content(test_file, test_id)
    else:
        print(f"Could not find {test_file}. Please check the path.")
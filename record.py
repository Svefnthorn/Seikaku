import sounddevice as sd
from scipy.io.wavfile import write
fs = 44100  # Sample rate
seconds = 3  # Duration of recording

print("Recording in 3...")
sd.sleep(1000)
print("2...")
sd.sleep(1000)
print("1...")
sd.sleep(1000)

print("--- SPEAK NOW ---")
myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
sd.wait()  # Wait until recording is finished
print("--- FINISHED ---")

write('test_input.wav', fs, myrecording)  # Save as WAV
print("Saved to 'test_input.wav'")


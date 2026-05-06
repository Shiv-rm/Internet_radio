# client_audio.py - Member 3
import pyaudio
from config import SAMPLE_RATE

class AudioPlayer:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        # Open a stream for 16-bit, Stereo, 44100Hz audio
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=2,
            rate=SAMPLE_RATE,
            output=True
        )

    def play(self, audio_data):
        """Writes raw bytes to the audio output buffer"""
        try:
            self.stream.write(audio_data)
        except Exception as e:
            print(f"Audio Playback Error: {e}")

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
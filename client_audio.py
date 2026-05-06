# client_audio.py - Member 3
# Handles audio playback with volume control and dynamic
# reconfiguration for different audio formats.
import pyaudio
import struct as _struct
from config import SAMPLE_RATE


class AudioPlayer:
    def __init__(self, channels=2, rate=SAMPLE_RATE):
        self.p = pyaudio.PyAudio()
        self._volume = 0.8
        self._channels = channels
        self._rate = rate
        self.stream = self._open_stream(channels, rate)

    def _open_stream(self, channels, rate):
        return self.p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            output=True
        )

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, val):
        self._volume = max(0.0, min(1.0, float(val)))

    def play(self, audio_data):
        if not audio_data:
            return
        try:
            if self._volume < 0.99:
                audio_data = self._apply_volume(audio_data)
            self.stream.write(audio_data)
        except Exception as e:
            print(f"Audio Playback Error: {e}")

    def _apply_volume(self, data):
        # Unpack 16-bit signed PCM samples, scale by volume, repack
        n = len(data) // 2
        samples = _struct.unpack(f'<{n}h', data)
        v = self._volume
        return _struct.pack(
            f'<{n}h',
            *(int(max(-32768, min(32767, s * v))) for s in samples)
        )

    def reconfigure(self, channels, rate):
        if channels == self._channels and rate == self._rate:
            return
        self.stream.stop_stream()
        self.stream.close()
        self._channels = channels
        self._rate = rate
        self.stream = self._open_stream(channels, rate)

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
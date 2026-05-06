# server.py - Member 1
# Multimedia broadcaster: streams audio (.wav) and video (.mp4/.avi)
# over UDP multicast using separate threads for each media type.
import socket
import time
import struct
import wave
import threading
import os
from config import (MCAST_GRP, MCAST_PORT, CHUNK_SIZE,
                    PKT_AUDIO, PKT_VIDEO,
                    VIDEO_FPS, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_QUALITY)


def find_media_files(directory="."):
    audio = [f for f in os.listdir(directory) if f.lower().endswith('.wav')]
    video = [f for f in os.listdir(directory) if f.lower().endswith(('.mp4', '.avi', '.mkv'))]
    audio.sort()
    video.sort()
    return audio, video


def audio_broadcast(sock, wav_files, seq_counter, lock):
    while True:
        for track in wav_files:
            print(f"🎵 Now Playing: {track}")
            wf = wave.open(track, 'rb')
            while True:
                data = wf.readframes(CHUNK_SIZE // 2)
                if not data:
                    break
                with lock:
                    seq = seq_counter[0]
                    seq_counter[0] += 1
                header = struct.pack("!IB", seq % 0xFFFFFFFF, PKT_AUDIO)
                sock.sendto(header + data, (MCAST_GRP, MCAST_PORT))
                time.sleep(0.02)
            wf.close()
        print("🔁 Audio playlist complete, looping...")


def video_broadcast(sock, video_path, seq_counter, lock):
    import cv2
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or VIDEO_FPS
    delay = 1.0 / min(fps, VIDEO_FPS)

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue
        frame = cv2.resize(frame, (VIDEO_WIDTH, VIDEO_HEIGHT))
        _, jpg = cv2.imencode('.jpg', frame,
                              [cv2.IMWRITE_JPEG_QUALITY, VIDEO_QUALITY])
        with lock:
            seq = seq_counter[0]
            seq_counter[0] += 1
        header = struct.pack("!IB", seq % 0xFFFFFFFF, PKT_VIDEO)
        sock.sendto(header + jpg.tobytes(), (MCAST_GRP, MCAST_PORT))
        time.sleep(delay)


def start_broadcast():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    audio_files, video_files = find_media_files()
    if not audio_files:
        print("Error: No .wav files found. Place a .wav file in this folder.")
        return

    print(f"📡 Broadcasting to {MCAST_GRP}:{MCAST_PORT}")
    print(f"📋 Audio: {', '.join(audio_files)}")

    seq_counter = [0]
    lock = threading.Lock()

    # Start audio thread
    t_audio = threading.Thread(target=audio_broadcast,
                               args=(sock, audio_files, seq_counter, lock),
                               daemon=True)
    t_audio.start()

    # Start video thread if video files found
    if video_files:
        print(f"🎬 Video: {video_files[0]}")
        t_video = threading.Thread(target=video_broadcast,
                                   args=(sock, video_files[0], seq_counter, lock),
                                   daemon=True)
        t_video.start()
    else:
        print("📻 Audio-only mode (no video files found)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n📡 Broadcast stopped.")
    finally:
        sock.close()


if __name__ == "__main__":
    start_broadcast()
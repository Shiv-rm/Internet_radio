# server.py - Member 1
import socket
import time
import struct
import wave
from config import MCAST_GRP, MCAST_PORT, CHUNK_SIZE

def start_broadcast(file_path):
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # Set Time-to-Live to 2 (allows it to pass through 2 routers/hops)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    try:
        wf = wave.open(file_path, 'rb')
        print(f"📡 Radio Station Live: Broadcasting to {MCAST_GRP}:{MCAST_PORT}")
        
        packet_count = 0
        while True:
            data = wf.readframes(CHUNK_SIZE // 2)
            if not data:
                wf.rewind() # Loop audio when finished
                continue
            
            # HEADER LOGIC (Extra Grade): Pack the sequence number into bytes
            header = struct.pack("!I", packet_count % 0xFFFFFFFF)
            packet = header + data
            
            sock.sendto(packet, (MCAST_GRP, MCAST_PORT))
            packet_count += 1
            
            # Control the flow to match real-time audio speed
            time.sleep(0.02) 
            
    except FileNotFoundError:
        print("Error: music.wav not found. Please place a wav file in this folder.")
    finally:
        sock.close()

if __name__ == "__main__":
    start_broadcast("music.wav")
# config.py - Shared by all members
MCAST_GRP = '224.1.1.1'
MCAST_PORT = 5007
CHUNK_SIZE = 1024  # Size of audio data per packet
HEADER_SIZE = 4    # 4 bytes for the Sequence Number (Extra Grade Feature)
SAMPLE_RATE = 44100 # Standard CD quality audio
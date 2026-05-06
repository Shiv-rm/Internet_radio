# config.py - Shared constants for the multicast radio system
MCAST_GRP     = '224.1.1.1'
MCAST_PORT    = 5007
CHUNK_SIZE    = 1024
HEADER_SIZE   = 5       # 4 bytes seq + 1 byte packet type
SAMPLE_RATE   = 44100

# Packet types
PKT_AUDIO     = 0x01
PKT_VIDEO     = 0x02

# Video settings
VIDEO_FPS     = 15
VIDEO_WIDTH   = 320
VIDEO_HEIGHT  = 240
VIDEO_QUALITY = 50      # JPEG compression (0-100)
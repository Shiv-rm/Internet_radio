# client_network.py - Member 2
import socket
import struct
from config import MCAST_GRP, MCAST_PORT, HEADER_SIZE

class NetworkReceiver:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_REUSEPORT lets multiple client processes on the same machine all
        # bind port 5007 and independently receive the multicast stream
        if hasattr(socket, "SO_REUSEPORT"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.sock.bind(('', MCAST_PORT))
        
        # Tell the OS to join the specific multicast group
        mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        self.expected_seq = 0
        self.lost_packets = 0

    def receive_packet(self):
        # Receive raw packet (Header + Audio)
        data, addr = self.sock.recvfrom(2048)
        
        # Extract Sequence Number
        header = data[:HEADER_SIZE]
        seq_num = struct.unpack("!I", header)[0]
        
        # Extract Audio Data
        audio_payload = data[HEADER_SIZE:]

        # QoS MONITORING (Extra Grade): Detect gaps in sequence numbers
        if self.expected_seq != 0 and seq_num > self.expected_seq:
            self.lost_packets += (seq_num - self.expected_seq)
        
        self.expected_seq = seq_num + 1
        return audio_payload, self.lost_packets
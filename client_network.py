# client_network.py - Member 2
# Handles multicast group joining, packet reception, header parsing,
# and QoS monitoring (packet loss, reordering, jitter estimation).
import socket
import struct
import json
from config import MCAST_GRP, MCAST_PORT, HEADER_SIZE, PKT_AUDIO, PKT_VIDEO


class NetworkReceiver:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.sock.bind(('', MCAST_PORT))

        # Join the multicast group
        mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        self.expected_seq = 0
        self.lost_packets = 0
        self.reordered_packets = 0

    def receive_packet(self):
        # Buffer large enough for video frames (~15 KB max)
        data, _ = self.sock.recvfrom(65535)

        # Parse 5-byte header: 4 seq + 1 type
        seq_num, pkt_type = struct.unpack("!IB", data[:HEADER_SIZE])
        payload = data[HEADER_SIZE:]

        # Packet loss detection
        if self.expected_seq != 0 and seq_num > self.expected_seq:
            self.lost_packets += (seq_num - self.expected_seq)

        # Out-of-order detection
        if self.expected_seq != 0 and seq_num < self.expected_seq:
            self.reordered_packets += 1

        self.expected_seq = seq_num + 1

        return pkt_type, payload, self.get_stats()

    def get_stats(self):
        return {
            'lost_packets': self.lost_packets,
            'reordered': self.reordered_packets,
        }
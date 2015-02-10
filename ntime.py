import argparse
import codecs
from ipaddress import IPv4Address
from select import select
from time import time, strftime, gmtime
from socket import socket, AF_INET, SOCK_DGRAM
from struct import pack, unpack
from decimal import Decimal


NTP_PORT = 123
DEFAULT_BUFFER_SIZE = 64 * 1024

NTP_CURRENT_VERSION = 4

NTP_HEADER_FORMAT = ">BBBBII4sQQQQ"
NTP_HEADER_LENGTH = 48
NTP_UTC_OFFSET = 2272060800


def utc_to_ntp_bytes(time):
    return int((Decimal(time) + NTP_UTC_OFFSET) * (2 ** 32))


def ntp_bytes_to_utc(value):
    return Decimal(value) / (2 ** 32) - NTP_UTC_OFFSET


def utc_to_string(value):
    return strftime("%a, %d %b %Y %H:%M:%S UTC", gmtime(value))


def from_ntp_short_bytes(value):
    return Decimal(value) / (2 ** 16)


class Packet(object):
    def __init__(self, leap=0, version=NTP_CURRENT_VERSION, mode=3, stratum=16, poll=0, precision=0, root_delay=0,
                 root_dispersion=0, ref_id=b'', ref_time=0, origin=0, receive=0,
                 transmit=0):
        self.leap = leap
        self.version = version
        self.mode = mode
        self.stratum = stratum
        self.poll = poll
        self.precision = precision
        self.root_delay = root_delay
        self.root_dispersion = root_dispersion
        self.ref_id = ref_id
        self.ref_time = ref_time
        self.origin = origin
        self.receive = receive
        self.transmit = transmit

    @classmethod
    def from_binary(cls, data):
        options, stratum, poll, precision, root_delay, root_dispersion, \
            ref_id, ref_time, origin, receive, transmit \
            = unpack(NTP_HEADER_FORMAT, data[:NTP_HEADER_LENGTH])
        leap, version, mode = options >> 6, ((options >> 3) & 0x7), options & 0x7
        return Packet(leap, version, mode, stratum, poll, precision, root_delay, root_dispersion, ref_id, ref_time,
                      origin, receive, transmit)

    @classmethod
    def form_request(cls, version=NTP_CURRENT_VERSION):
        current_time = time()
        return Packet(version=version, transmit=utc_to_ntp_bytes(current_time))

    def to_binary(self):
        return pack(NTP_HEADER_FORMAT,
                    (self.leap << 6) | (self.version << 3) | self.mode,
                    self.stratum, self.poll, self.precision,
                    self.root_delay,
                    self.root_dispersion,
                    self.ref_id,
                    self.ref_time,
                    self.origin,
                    self.receive,
                    self.transmit)

    def __str__(self):
        return "Version: %d\n" % self.version + \
            "Leap: %d\n" % self.leap + \
            "Mode: %d\n" % self.mode + \
            "Stratum: %d\n" % self.stratum + \
            "Poll: %lf (%d)\n" % (2 ** (-self.poll), self.poll) + \
            "Precision: %lf (%d)\n" % (2 ** (-self.precision), self.precision) + \
            "Root delay: %lf\n" % from_ntp_short_bytes(self.root_delay) + \
            "Root dispersion: %lf\n" % from_ntp_short_bytes(self.root_dispersion) + \
            "Reference ID: %s\n" % IPv4Address(self.ref_id) + \
            "Reference Timestamp: %s\n" % utc_to_string(ntp_bytes_to_utc(self.ref_time)) + \
            "Origin Timestamp: %s\n" % utc_to_string(ntp_bytes_to_utc(self.origin)) + \
            "Receive Timestamp: %s\n" % utc_to_string(ntp_bytes_to_utc(self.receive)) + \
            "Transmit Timestamp: %s\n" % utc_to_string(ntp_bytes_to_utc(self.transmit))


def get_args_parser():
    parser = argparse.ArgumentParser(description="NTP tool")
    parser.add_argument("source", help="Source server address")
    parser.add_argument("-v", "--version", help="NTP version to be used", default=NTP_CURRENT_VERSION, type=int)
    parser.add_argument("-t", "--timeout", help="Communication timeout in seconds (default 1)", default=1, type=int)
    parser.add_argument("-a", "--attempts", help="Maximum communication attempts (default 1)", default=1, type=int)
    return parser


def get_address(source):
    chunks = source.split(':')
    return chunks[0], int(chunks[1]) if len(chunks) > 1 else NTP_PORT


def get_packet(args):
    address = get_address(args.source)
    request = Packet.form_request(version=args.version).to_binary()
    for attempt in range(1, args.attempts + 1):
        with socket(AF_INET, SOCK_DGRAM) as sock:
            sock.sendto(request, address)
            if select([sock], [], [], args.timeout)[0]:
                return Packet.from_binary(sock.recvfrom(DEFAULT_BUFFER_SIZE)[0])
            print("Attempt %d failed" % attempt)


if __name__ == "__main__":
    parser = get_args_parser()
    args = parser.parse_args()
    received_packet = get_packet(args)
    if received_packet:
        print(received_packet)
    else:
        print("Failed to receive packet")

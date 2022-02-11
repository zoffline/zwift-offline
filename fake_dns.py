import socket

class DNSQuery:
    def __init__(self, data):
        self.data = data
        self.domain = ''
        t = (data[2] >> 3) & 15
        if t == 0:
            i = 12
            l = data[i]
            while l != 0:
                self.domain += data[i + 1:i + l + 1].decode('utf-8') + '.'
                i += l + 1
                l = data[i]

    def response(self, server_ip):
        packet = b''
        domains = ['us-or-rly101.zwift.com.', 'secure.zwift.com.']
        if self.domain:
            if self.domain in domains:
                ip = server_ip
            else:
                ip = socket.gethostbyname_ex(self.domain)[2][0]
            packet += self.data[:2] + b'\x81\x80'
            packet += self.data[4:6] + self.data[4:6] + b'\x00\x00\x00\x00'
            packet += self.data[12:]
            packet += b'\xc0\x0c'
            packet += b'\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'
            packet += bytearray.fromhex('{:02X}{:02X}{:02X}{:02X}'.format(*map(int, ip.split('.'))))
            return packet

def fake_dns(server_ip):
    udps = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udps.bind(('', 53))
    while True:
        data, addr = udps.recvfrom(1024)
        p = DNSQuery(data)
        udps.sendto(p.response(server_ip), addr)

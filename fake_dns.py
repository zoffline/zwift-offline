import dns.resolver
import socketserver
import os

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

    def response(self):
        packet = b''
        if self.domain:
            name = self.domain
            namemap = DNSServer.namemap
            if namemap.__contains__(name):
                ip = namemap[name]
            else:
                answer = DNSServer.resolver.cache.data.get((name, 1, 1))
                if not answer:
                    answer = DNSServer.resolver.resolve(name)
                    DNSServer.resolver.cache.put((name, 1, 1), answer)
                ip = answer[0].to_text()
            packet += self.data[:2] + b'\x81\x80'
            packet += self.data[4:6] + self.data[4:6] + b'\x00\x00\x00\x00'
            packet += self.data[12:]
            packet += b'\xc0\x0c'
            packet += b'\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04'
            packet += bytes(map(int, ip.split('.')))
        return packet

class DNSUDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        try:
            query = DNSQuery(data)
            socket.sendto(query.response(), self.client_address)
        except Exception as e:
            print('fake_dns: %s' % repr(e))

class DNSServer:
    def __init__(self, port=53):
        DNSServer.namemap = {}
        DNSServer.resolver = dns.resolver.Resolver(configure=False)
        DNSServer.resolver.nameservers = ['8.8.8.8', '8.8.4.4']
        DNSServer.resolver.cache = dns.resolver.Cache()
        self.port = port
    def addname(self, name, ip):
        DNSServer.namemap[name] = ip
    def start(self):
        HOST = os.environ.get('ZOFFLINE_SERVER_HOST', '')
        PORT = self.port
        server = socketserver.ThreadingUDPServer((HOST, PORT), DNSUDPHandler)
        server.serve_forever()

def fake_dns(server_ip):
    dns = DNSServer()
    dns.addname('secure.zwift.com.', server_ip)
    dns.addname('us-or-rly101.zwift.com.', server_ip)
    dns.start()

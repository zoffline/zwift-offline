import dns.message
import dns.rdata
import dns.rdataclass
import dns.rdatatype
import dns.resolver
import socketserver
import os

class DNSUDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        query = dns.message.from_wire(data)
        response = dns.message.make_response(query)
        for question in query.question:
            rdtype = question.rdtype
            if not rdtype in [dns.rdatatype.A, dns.rdatatype.AAAA]:
                continue
            name = question.name.to_text()
            if name in DNSServer.namemap:
                ip = DNSServer.namemap[name]
                if (rdtype == dns.rdatatype.A and not '.' in ip) or (rdtype == dns.rdatatype.AAAA and not ':' in ip):
                    continue
            else:
                try:
                    answer = DNSServer.resolver.cache.data.get((name, rdtype, dns.rdataclass.IN))
                    if not answer:
                        answer = DNSServer.resolver.resolve(name, rdtype)
                        DNSServer.resolver.cache.put((name, rdtype, dns.rdataclass.IN), answer)
                    ip = answer[0].to_text()
                except:
                    continue
            rdata = dns.rdata.from_text(dns.rdataclass.IN, rdtype, ip)
            rrset = dns.rrset.from_rdata(name, 3600, rdata)
            response.answer.append(rrset)
        socket.sendto(response.to_wire(), self.client_address)

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

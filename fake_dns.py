import dns.message
import dns.rdata
import dns.resolver
import socketserver
import os

class DNSUDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        try:
            query = dns.message.from_wire(data)
            response = dns.message.make_response(query)
            for question in query.question:
                name = question.name.to_text()
                if name in DNSServer.namemap and question.rdtype == 1:
                    ip = DNSServer.namemap[name]
                else:
                    answer = DNSServer.resolver.cache.data.get((name, 1, 1))
                    if not answer:
                        answer = DNSServer.resolver.resolve(name)
                        DNSServer.resolver.cache.put((name, 1, 1), answer)
                    ip = answer[0].to_text()
                rdata = dns.rdata.from_text(1, 1, ip)
                rrset = dns.rrset.RRset(question.name, 1, 1)
                rrset.add(rdata)
                response.answer.append(rrset)
            socket.sendto(response.to_wire(), self.client_address)
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

using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using System.Net.Http.Json;
using System.Net.Sockets;
using System.Threading;
using System.Security.Cryptography.X509Certificates;
using System.Net.Security;
using System.Security.Authentication;
using System.IO;

namespace ConsoleApp1 {
    public class SslMitm {
        static X509Certificate serverCertificate = new X509Certificate(@"cert-zwift-com.pfx", pwd_here);
        public static void Start() {
            void server() {
                TcpListener listener = new TcpListener(IPAddress.Any, 443);
                listener.Start();
                Console.WriteLine("SSL:443. Waiting for clients to connect...");
                while (true) {
                    TcpClient client = listener.AcceptTcpClient();
                    new Thread(o => { ProcessClient(client); }).Start();
                }
                void ProcessClient(TcpClient client) {
                    SslStream sslStream = new SslStream(client.GetStream(), false);
                    TcpClient fwdClient = new TcpClient("13.33.246.64", 443);
                    SslStream sslForwardStream = new SslStream(fwdClient.GetStream(), false, null, null);
                    try {
                        sslForwardStream.AuthenticateAsClient("us-or-rly101.zwift.com");
                    }
                    catch (AuthenticationException e)
                    {
                        Console.WriteLine("ProcessClient Exception: {0}", e.Message);
                        if (e.InnerException != null) {
                            Console.WriteLine("Inner exception: {0}", e.InnerException.Message);
                        }
                        fwdClient.Close();
                        return;
                    }
                    var stage = "?";
                    try {
                        sslStream.AuthenticateAsServer(serverCertificate, clientCertificateRequired: false, checkCertificateRevocation: false);
                        sslStream.ReadTimeout = 1500;
                        sslForwardStream.ReadTimeout = 1500;
                        sslStream.WriteTimeout = 1500;
                        sslForwardStream.WriteTimeout = 1500;

                        byte[] buffer = new byte[65536];
                        while(client.Connected && fwdClient.Connected) {
                            int bytes = -1;
                            while (client.Connected && fwdClient.Connected) {
                                stage = "SR";
                                bytes = sslStream.Read(buffer, 0, buffer.Length);
                                if (bytes > 0) {
                                    stage = "FW";
                                    sslForwardStream.Write(buffer, 0, bytes);
                                    using (var s = new FileStream(path_here + Thread.CurrentThread.ManagedThreadId.ToString(), FileMode.Append)) {
                                        s.Write(buffer, 0, bytes);
                                    }
                                }
                                if(bytes < buffer.Length) break;
                            }
                            if(bytes != -1)
                                sslForwardStream.Flush();
                            bytes = -1;
                            while (client.Connected && fwdClient.Connected) {
                                stage = "FR";
                                bytes = sslForwardStream.Read(buffer, 0, buffer.Length);
                                if (bytes > 0) {
                                    stage = "SW";
                                    sslStream.Write(buffer, 0, bytes);
                                    using (var s = new FileStream(path_here + Thread.CurrentThread.ManagedThreadId.ToString(), FileMode.Append)) {
                                        s.Write(buffer, 0, bytes);
                                    }
                                }
                                if (bytes < buffer.Length) break;
                            }
                            if (bytes != -1)
                                sslStream.Flush();
                        }
                    } catch (Exception) {
                        Console.WriteLine("SSL Client Exception: {0}", stage);
                        try { sslForwardStream.Flush(); } catch (Exception) { }
                        try { sslStream.Flush();} catch (Exception) { }
                        try { sslStream.Close();} catch (Exception) { }
                        try { client.Close();} catch (Exception) { }
                        try { sslForwardStream.Close();} catch (Exception) { }
                        try { fwdClient.Close();} catch (Exception) { }
                        return;
                    } finally {
                        try { sslStream.Close(); } catch (Exception) { }
                        try { client.Close(); } catch (Exception) { }
                        try { sslForwardStream.Close(); } catch (Exception) { }
                        try { fwdClient.Close(); } catch (Exception) { }
                    }
                }
            }
            new Thread(server).Start();
        }
    }
    public class Bearer {
        public string access_token { get; set; }
    }
    public class User {
        public int id { get; set; } = your_id_here;
    }
    public class MobileEnv { 
        public int appBuild { get; set; }
        public string appDisplayName { get; set; }
        public string appVersion { get; set; }
        public string systemHardware { get; set; }
        public string systemOS { get; set; }
        public string systemOSVersion { get; set; }
    }
    public class PhoneInfo {
        public static PhoneInfo Create() {
            return new PhoneInfo() {
                mobileEnvironment = new MobileEnv { appBuild = 1276, appDisplayName = "Companion", appVersion = "3.29.0", systemHardware = "samsung SM-G965N", systemOS = "Android", systemOSVersion = "7.1.2 (API 25)" },
                phoneAddress = GetLocalIPAddress(),
                port = 21587,
                protocol = "TCP"
            };
        }
        public string phoneAddress { get; set; }
        public string protocol { get; set; }
        public MobileEnv mobileEnvironment { get; set; }
        public int port { get; set; }
        public static string GetLocalIPAddress() {
            var host = Dns.GetHostEntry(Dns.GetHostName());
            foreach (var ip in host.AddressList)
                if (ip.AddressFamily == AddressFamily.InterNetwork)
                    return ip.ToString();
            throw new Exception("No network adapters with an IPv4 address in the system!");
        }
    }
    internal class Program {
        static void Main(string[] args) {
            //SslMitm.Start(); return;

            Bearer bearer = Authorize();
            var me = new User();
            var pi = PhoneInfo.Create();
            using (var httpClient = NewAuthorizedHttpClient(bearer)) {
                me = httpClient.GetFromJsonAsync<User>("api/profiles/me").Result;
                httpClient.PutAsJsonAsync<PhoneInfo>("relay/profiles/me/phone", pi).Wait();
                //pi = httpClient.GetFromJsonAsync<PhoneInfo>("relay/profiles/me/phone").Result; //почему-то тут NULL
                //Console.WriteLine($"phoneAddress: {pi.phoneAddress}:{pi.port}");
            }
            TcpListener server = new TcpListener(IPAddress.Any, pi.port);
            Console.WriteLine($"Listening: {pi.phoneAddress}:{pi.port}");
            server.Start();
            //byte cnt = 0;
            while (true) {
                TcpClient client = server.AcceptTcpClient();
                NetworkStream ns = client.GetStream();
                Console.WriteLine($"New client: {client.Client.RemoteEndPoint.ToString()}");
                while (client.Connected) {
                    int msgSize = ((int)ns.ReadByte() << 24) + ((int)ns.ReadByte() << 16) + ((int)ns.ReadByte() << 8) + ns.ReadByte();
                    if (msgSize > 0) {
                        Console.WriteLine($"Msg size: {msgSize}");
                        byte[] payload = new byte[msgSize];
                        int r = ns.Read(payload, 0, msgSize);
                        if (r != msgSize)
                            Console.WriteLine($"Wrond read: {r}");
                        else
                            Console.WriteLine(BitConverter.ToString(payload));
                        //ns.Write(new byte[] { 0, 0, 0, 13, 0x08, 0xAD, 0xfb, 0x89, 0x02, 0x12, 0x02, 0x50, 0x01 }, 0, 13);
                        //ns.Write(new byte[] { 0, 0, 0, 14, 0x08, 0x01, 0x12, 0x06, 0x08, cnt++, 0x10, 0x01, 0x50, 0x01 }, 0, 14);
                        //ns.Flush();
                    }
                }
            }
            HttpClient NewHttpClient(string baseAddr) { return new HttpClient(NewClientHandler()) { BaseAddress = new Uri(baseAddr) }; }
            HttpClientHandler NewClientHandler() { return new HttpClientHandler() { 
                //Proxy = new WebProxy("127.0.0.1:8888", false) 
            }; }
            HttpClient NewAuthorizedHttpClient(Bearer auth) {
                var ret = NewHttpClient("https://us-or-rly101.zwift.com/");
                ret.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", auth.access_token);
                ret.DefaultRequestHeaders.TryAddWithoutValidation("Content-Type", "application/json");
                ret.DefaultRequestHeaders.TryAddWithoutValidation("Accept", "application/json");
                ret.DefaultRequestHeaders.TryAddWithoutValidation("Accept-Encoding", "gzip");
                ret.DefaultRequestHeaders.TryAddWithoutValidation("Zwift-Api-Version", "2.6");
                ret.DefaultRequestHeaders.TryAddWithoutValidation("User-Agent", "com.zwift.android.prod/3.29.0-1276 (samsung SM-G965N/Android 7.1.2)");// loggedInUserId=" + me.id.ToString());
                ret.DefaultRequestHeaders.Connection.Add("keep-alive");
                ret.DefaultRequestHeaders.ExpectContinue = false;
                return ret;
            }
            Bearer Authorize() {
                while(true) try {
                    using (var httpClient = NewHttpClient("https://secure.zwift.com/")) {
                        var pwdContent = new FormUrlEncodedContent(new[] {
                            new KeyValuePair<string, string>("client_id", "Zwift_Mobile_Link"),
                            new KeyValuePair<string, string>("username", your_login),
                            new KeyValuePair<string, string>("password", your_pwd),
                            new KeyValuePair<string, string>("grant_type", "password")
                        });
                        using (var tokeInfo = httpClient.PostAsync("auth/realms/zwift/protocol/openid-connect/token", pwdContent).Result) {
                            tokeInfo.EnsureSuccessStatusCode();
                            return tokeInfo.Content.ReadFromJsonAsync<Bearer>().Result;
                        }
                    } 
                } catch (Exception ex) {
                    Console.WriteLine("Connection failed: {0} {1}. Repeat...", ex.GetType().Name, (ex.InnerException != null) ? ex.InnerException.GetType().Name : "");
                }
            }
        }
    }
}

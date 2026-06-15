import http.server
import socketserver
import json
import urllib.request

PORT = 8080

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        print("Intercepted request for model:", data.get('model'))
        # Rewrite model
        data['model'] = 'google/gemini-2.5-flash'
        
        req = urllib.request.Request('https://openrouter.ai/api/v1/chat/completions', data=json.dumps(data).encode('utf-8'))
        req.add_header('Content-Type', 'application/json')
        req.add_header('Authorization', self.headers['Authorization'])
        
        try:
            with urllib.request.urlopen(req) as response:
                resp_data = response.read()
                self.send_response(response.status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(resp_data)
                print("Forwarded response successfully.")
        except urllib.error.HTTPError as e:
            print("HTTPError:", e.code, e.read())
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            print("Error:", e)
            self.send_response(500)
            self.end_headers()

with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()

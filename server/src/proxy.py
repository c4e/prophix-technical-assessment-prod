"""Local SigV4 proxy — forwards MCP Inspector requests to the deployed AgentCore endpoint.

Usage:
    AWS_PROFILE=bbl-training-prod python -m src.proxy

Then point MCP Inspector at: http://localhost:9000/mcp  (Streamable HTTP, no auth)
"""

import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import urllib.request
import urllib.error
import urllib.parse

REGION = os.getenv("AWS_REGION", "us-west-2")
AGENT_ARN = os.getenv(
    "AGENT_ARN",
    "arn:aws:bedrock-agentcore:us-west-2:108782061904:runtime/server-7iBhkG30on",
)
QUALIFIER = os.getenv("QUALIFIER", "DEFAULT")

ENCODED_ARN = urllib.parse.quote(AGENT_ARN, safe="")
ENDPOINT = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{ENCODED_ARN}/invocations?qualifier={QUALIFIER}"

PROXY_PORT = int(os.getenv("PROXY_PORT", "9000"))

session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()


class ProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        forward_headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "Accept": self.headers.get("Accept", "application/json, text/event-stream"),
        }

        session_id = self.headers.get("Mcp-Session-Id")
        if session_id:
            forward_headers["Mcp-Session-Id"] = session_id

        aws_request = AWSRequest(
            method="POST",
            url=ENDPOINT,
            data=body,
            headers=forward_headers,
        )
        SigV4Auth(credentials, "bedrock-agentcore", REGION).add_auth(aws_request)

        req = urllib.request.Request(
            ENDPOINT,
            data=body,
            headers=dict(aws_request.headers),
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for key in ("Content-Type", "Mcp-Session-Id"):
                    val = resp.getheader(key)
                    if val:
                        self.send_header(key, val)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            error_body = e.read()
            print(f"[proxy] upstream {e.code}: {error_body.decode(errors='replace')}")
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(error_body)))
            self.end_headers()
            self.wfile.write(error_body)
        except Exception as e:
            msg = json.dumps({"error": str(e)}).encode()
            print(f"[proxy] error: {e}")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"SigV4 proxy for AgentCore MCP. POST to /mcp\n")

    def do_DELETE(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[proxy] {args[0]}")


if __name__ == "__main__":
    print(f"SigV4 Proxy for AgentCore MCP Server")
    print(f"  Upstream: {ENDPOINT[:80]}...")
    print(f"  Listening: http://localhost:{PROXY_PORT}/mcp")
    print(f"  Region: {REGION}")
    print()
    print("Point MCP Inspector at: http://localhost:9000/mcp (Streamable HTTP, no auth)")
    print()
    httpd = HTTPServer(("0.0.0.0", PROXY_PORT), ProxyHandler)
    httpd.serve_forever()

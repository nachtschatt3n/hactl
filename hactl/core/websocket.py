"""
WebSocket client for Home Assistant API
"""

import os
import ssl
import socket
import base64
import json
import struct
import click
from urllib.parse import urlparse


class WebSocketClient:
    """Simple WebSocket client for Home Assistant API"""

    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.sock = None
        self.req_id = 1

    def connect(self):
        """Connect to WebSocket and authenticate"""
        parsed = urlparse(self.url)
        if parsed.scheme not in ('http', 'https'):
            raise click.ClickException('Unsupported scheme in HASS_URL')

        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        path = parsed.path.rstrip('/') + '/api/websocket'

        self.sock = socket.create_connection((host, port))
        if parsed.scheme == 'https':
            context = ssl.create_default_context()
            self.sock = context.wrap_socket(self.sock, server_hostname=host)

        # WebSocket handshake
        key = base64.b64encode(os.urandom(16)).decode()
        req = f"GET {path} HTTP/1.1\r\n" \
              f"Host: {host}\r\n" \
              "Upgrade: websocket\r\n" \
              "Connection: Upgrade\r\n" \
              f"Sec-WebSocket-Key: {key}\r\n" \
              "Sec-WebSocket-Version: 13\r\n" \
              f"Origin: {self.url}\r\n\r\n"
        self.sock.sendall(req.encode())

        buffer = b''
        while b"\r\n\r\n" not in buffer:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise click.ClickException('WebSocket handshake failed')
            buffer += chunk
        if b" 101 " not in buffer:
            raise click.ClickException('WebSocket handshake unsuccessful:\n' + buffer.decode(errors='ignore'))

        # Authenticate
        self.send_frame(json.dumps({"type": "auth", "access_token": self.token}).encode())
        while True:
            msg = self.recv_json()
            if msg.get('type') == 'auth_ok':
                break
            if msg.get('type') == 'auth_required':
                continue
            if msg.get('type') == 'auth_invalid':
                raise click.ClickException('Authentication failed')

    def recv_exact(self, n):
        """Receive exactly n bytes"""
        data = b''
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise click.ClickException('Socket closed unexpectedly')
            data += chunk
        return data

    def recv_frame(self):
        """Receive a WebSocket frame"""
        header = self.recv_exact(2)
        b1, b2 = header
        opcode = b1 & 0x0F
        masked = b2 & 0x80
        length = b2 & 0x7F
        if length == 126:
            length = struct.unpack('>H', self.recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack('>Q', self.recv_exact(8))[0]
        mask = self.recv_exact(4) if masked else None
        payload = self.recv_exact(length)
        if masked and mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def send_frame(self, data: bytes):
        """Send a WebSocket frame"""
        length = len(data)
        header = bytearray()
        header.append(0x81)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header.extend(struct.pack('>H', length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack('>Q', length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def recv_json(self):
        """Receive JSON message"""
        while True:
            opcode, payload = self.recv_frame()
            if opcode == 0x8:
                raise click.ClickException('WebSocket closed by server')
            if opcode == 0x1:
                try:
                    return json.loads(payload.decode())
                except json.JSONDecodeError:
                    continue

    def call(self, message_type, **kwargs):
        """Call WebSocket API"""
        self.req_id += 1
        message = {"id": self.req_id, "type": message_type, **kwargs}
        self.send_frame(json.dumps(message).encode())
        while True:
            msg = self.recv_json()
            if msg.get('id') == self.req_id:
                if not msg.get('success', False):
                    raise click.ClickException(f"WebSocket call failed: {msg}")
                return msg.get('result')

    def close(self):
        """Close WebSocket connection"""
        if self.sock:
            self.sock.close()

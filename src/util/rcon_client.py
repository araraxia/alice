"""
Minimal Source RCON client for sending console commands to a Minecraft server.

Credentials are loaded from conf/cred/minecraft_rcon.json:
{
    "host": "192.168.1.50",
    "port": 25575,
    "password": "rcon.password from server.properties",
    "timeout": 5
}

Usage:
    with RconClient.from_config() as rcon:
        response = rcon.command("list")

Note: responses longer than one packet (~4KB) are truncated to the first packet.
"""

from pathlib import Path
import json
import socket
import struct

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEF_CRED_PATH = ROOT_DIR / "conf" / "cred" / "minecraft_rcon.json"

SERVERDATA_AUTH = 3
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_RESPONSE_VALUE = 0


class RconError(Exception):
    pass


class RconClient:
    def __init__(self, host: str, port: int, password: str, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.sock = None
        self._request_id = 0

    @classmethod
    def from_config(cls, config_path: Path = DEF_CRED_PATH):
        with Path(config_path).open("r") as f:
            config = json.load(f)
        return cls(
            host=config["host"],
            port=int(config.get("port", 25575)),
            password=config["password"],
            timeout=float(config.get("timeout", 5)),
        )

    def __enter__(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as e:
            raise RconError(f"Could not connect to {self.host}:{self.port}: {e}") from e
        try:
            self._login()
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def command(self, cmd: str) -> str:
        """Send a console command and return the server's response text."""
        request_id = self._send(SERVERDATA_EXECCOMMAND, cmd)
        response_id, _, body = self._read_packet()
        if response_id != request_id:
            raise RconError(f"Unexpected RCON response id {response_id}")
        return body

    def _login(self):
        request_id = self._send(SERVERDATA_AUTH, self.password)
        response_id, packet_type, _ = self._read_packet()
        # Some servers send an empty RESPONSE_VALUE packet before the auth response
        if packet_type == SERVERDATA_RESPONSE_VALUE:
            response_id, _, _ = self._read_packet()
        if response_id == -1 or response_id != request_id:
            raise RconError("RCON authentication failed")

    def _send(self, packet_type: int, payload: str) -> int:
        self._request_id += 1
        data = (
            struct.pack("<ii", self._request_id, packet_type)
            + payload.encode("utf-8")
            + b"\x00\x00"
        )
        try:
            self.sock.sendall(struct.pack("<i", len(data)) + data)
        except OSError as e:
            raise RconError(f"Failed to send RCON packet: {e}") from e
        return self._request_id

    def _read_packet(self):
        (length,) = struct.unpack("<i", self._recv_exact(4))
        data = self._recv_exact(length)
        request_id, packet_type = struct.unpack("<ii", data[:8])
        body = data[8:-2].decode("utf-8", errors="replace")
        return request_id, packet_type, body

    def _recv_exact(self, size: int) -> bytes:
        buf = b""
        while len(buf) < size:
            try:
                chunk = self.sock.recv(size - len(buf))
            except OSError as e:
                raise RconError(f"Failed to read RCON response: {e}") from e
            if not chunk:
                raise RconError("RCON connection closed by server")
            buf += chunk
        return buf

"""Send Python code to the live Blender MCP socket server and return the result."""
import socket, json, sys

def send(code, host="localhost", port=9876, timeout=120):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((host, port))
        msg = json.dumps({"type": "execute_code", "params": {"code": code}})
        s.sendall(msg.encode())
        chunks = []
        while True:
            try:
                chunk = s.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                try:
                    json.loads(b"".join(chunks).decode())
                    break
                except json.JSONDecodeError:
                    continue
            except socket.timeout:
                break
        raw = b"".join(chunks).decode()
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw}

if __name__ == "__main__":
    code = sys.stdin.read() if not sys.argv[1:] else " ".join(sys.argv[1:])
    result = send(code)
    print(json.dumps(result, indent=2))

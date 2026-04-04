import socket
import threading
import struct
import argparse
import time
import json
from datetime import datetime

TCP_PORT = 50000
UDP_PORT = 50001
BUFFER_SIZE = 4096

MSG_TEXT = 1
MSG_NAME = 2
MSG_REQ_HISTORY = 3
MSG_HISTORY_DATA = 4


class P2PChat:
    def __init__(self, ip, name):
        self.ip = ip
        self.name = name
        self.peers = {}
        self.history = []
        self.lock = threading.Lock()
        self.history_synced = False#флаг, чтобы не качать историю дважды

        self.add_history(f"Узел запущен. IP: {self.ip}, Имя: {self.name}")

    def add_history(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        with self.lock:
            self.history.append(log_entry)
            print(log_entry)

    def pack_msg(self, msg_type, payload=""):
        payload_bytes = payload.encode('utf-8')
        header = struct.pack('!BI', msg_type, len(payload_bytes))
        return header + payload_bytes

    def send_to_peer(self, sock, msg_type, payload=""):
        try:
            sock.sendall(self.pack_msg(msg_type, payload))
        except Exception:
            pass

    def broadcast_udp(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = f"{self.ip}:{self.name}".encode('utf-8')

        for i in range(1, 11):
            target_ip = f"127.0.0.{i}"
            if target_ip != self.ip:
                try:
                    udp_sock.sendto(msg, (target_ip, UDP_PORT))
                except Exception:
                    pass
        udp_sock.close()

    def listen_udp(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        udp_sock.bind((self.ip, UDP_PORT))

        while True:
            data, addr = udp_sock.recvfrom(BUFFER_SIZE)
            msg_str = data.decode('utf-8')

            if ":" in msg_str:
                peer_ip, peer_name = msg_str.split(":", 1)

                with self.lock:
                    is_known = peer_ip in self.peers

                if peer_ip != self.ip and not is_known:
                    self.connect_to_peer(peer_ip, peer_name)

    def start_tcp_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.ip, TCP_PORT))
        server.listen(10)

        while True:
            client_sock, addr = server.accept()
            threading.Thread(target=self.handle_tcp_client, args=(client_sock, addr[0]), daemon=True).start()

    def connect_to_peer(self, peer_ip, peer_name):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer_ip, TCP_PORT))

            with self.lock:
                self.peers[peer_ip] = {"socket": sock, "name": peer_name}

            self.send_to_peer(sock, MSG_NAME, f"{self.ip}:{self.name}")
            self.add_history(f"Установлено соединение с: {peer_name} ({peer_ip})")

            threading.Thread(target=self.handle_tcp_client, args=(sock, peer_ip), daemon=True).start()
        except Exception as e:
            self.add_history(f"Не удалось подключиться к {peer_ip}: {e}")

    def handle_tcp_client(self, sock, temp_peer_ip):
        peer_ip = temp_peer_ip
        peer_name = "Unknown"
        try:
            while True:
                header = sock.recv(5)
                if not header:
                    break

                msg_type, msg_length = struct.unpack('!BI', header)

                payload_bytes = b""
                while len(payload_bytes) < msg_length:
                    chunk = sock.recv(msg_length - len(payload_bytes))
                    if not chunk:
                        break
                    payload_bytes += chunk

                payload = payload_bytes.decode('utf-8')

                if msg_type == MSG_NAME:
                    if ":" in payload:
                        real_ip, real_name = payload.split(":", 1)
                        peer_ip = real_ip
                        peer_name = real_name
                    else:
                        peer_name = payload

                    with self.lock:
                        self.peers[peer_ip] = {"socket": sock, "name": peer_name}

                    self.add_history(f"К нам подключился: {peer_name} ({peer_ip})")

                    #запрос истории (только 1 раз)
                    if not self.history_synced and len(self.history) <= 2:
                        self.history_synced = True
                        self.send_to_peer(sock, MSG_REQ_HISTORY)

                elif msg_type == MSG_TEXT:
                    self.add_history(f"[{peer_name}]: {payload}")

                elif msg_type == MSG_REQ_HISTORY:
                    with self.lock:
                        hist_data = json.dumps(self.history)
                    self.send_to_peer(sock, MSG_HISTORY_DATA, hist_data)

                elif msg_type == MSG_HISTORY_DATA:
                    received_history = json.loads(payload)
                    self.add_history("Получена история чата:")
                    for item in received_history:
                        print(f" * {item}")
                    self.add_history("\n")

        except ConnectionResetError:
            pass
        finally:
            with self.lock:
                if peer_ip in self.peers:
                    del self.peers[peer_ip]
            self.add_history(f"Узел покинул чат: {peer_name} ({peer_ip})")
            sock.close()

    def run(self):
        threading.Thread(target=self.start_tcp_server, daemon=True).start()
        threading.Thread(target=self.listen_udp, daemon=True).start()

        time.sleep(0.5)
        self.broadcast_udp()

        while True:
            try:
                msg = input()
                if msg.strip() == "":
                    continue
                if msg.lower() in ['exit', 'quit', '/q']:
                    break

                self.add_history(f"[Вы]: {msg}")

                with self.lock:
                    if not self.peers:
                        print("(Системно: В чате пока никого нет, сообщение никто не получил)")
                    else:
                        for p_ip, peer_data in self.peers.items():
                            self.send_to_peer(peer_data["socket"], MSG_TEXT, msg)
            except KeyboardInterrupt:
                break

        print("Завершение работы чата")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P2P Чат")
    parser.add_argument("--ip", required=True, help="Ваш IP (например, 127.0.0.1)")
    parser.add_argument("--name", required=True, help="Ваше имя")
    args = parser.parse_args()

    chat = P2PChat(args.ip, args.name)
    chat.run()
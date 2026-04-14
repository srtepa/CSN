import socket
import threading
import select
from urllib.parse import urlparse
import os

HOST = '0.0.0.0'
PORT = 8888
BUFFER_SIZE = 8192
BLACKLIST_FILE = 'blacklist.txt'


def load_blacklist():
    if not os.path.exists(BLACKLIST_FILE):
        return []
    with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
        return [line.strip().lower() for line in f if line.strip()]


def get_error_page(url):
    body = f"""<html>
        <head><title>Access Denied</title></head>
        <body style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h1 style="color: red;">Доступ запрещен!</h1>
            <p>Запрашиваемый ресурс <b>{url}</b> находится в черном списке прокси-сервера.</p>
        </body>
    </html>"""

    body_bytes = body.encode('utf-8')
    headers = (
        "HTTP/1.1 403 Forbidden\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(body_bytes)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    return headers.encode('utf-8') + body_bytes


def handle_client(client_socket, client_address, blacklist):
    try:
        request_data = client_socket.recv(BUFFER_SIZE)
        if not request_data:
            return

        #парсинг первой строки запроса
        headers = request_data.split(b'\r\n')
        first_line = headers[0].decode('utf-8', errors='ignore')

        try:
            method, full_url, http_version = first_line.split(' ')
        except ValueError:
            return

        #парсинг URL
        parsed_url = urlparse(full_url)
        hostname = parsed_url.hostname
        port = parsed_url.port or 80

        #относительный путь
        path = parsed_url.path or "/"
        if parsed_url.query:
            path += "?" + parsed_url.query

        if any(blocked_item in full_url.lower() for blocked_item in blacklist):
            print(f"[BLOCKED] {full_url}")
            client_socket.sendall(get_error_page(full_url))
            return

        #новая первая строка запроса с относительным путем
        new_first_line = f"{method} {path} {http_version}".encode('utf-8')

        modified_headers = [new_first_line]
        for header in headers[1:]:
            if header.lower().startswith(b'proxy-connection:') or header.lower().startswith(b'connection:'):
                modified_headers.append(b'Connection: close')
            else:
                modified_headers.append(header)

        new_request_data = b'\r\n'.join(modified_headers)

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.settimeout(10)
        server_socket.connect((hostname, port))

        server_socket.sendall(new_request_data)

        first_chunk = True

        #select для двунаправленной передачи
        sockets = [client_socket, server_socket]
        while True:
            readable, _, _ = select.select(sockets, [], [], 10)
            if not readable:
                break

            for sock in readable:
                data = sock.recv(BUFFER_SIZE)
                if not data:
                    sockets.remove(sock)
                    continue

                if sock is server_socket:
                    if first_chunk:
                        try:
                            resp_first_line = data.split(b'\r\n')[0].decode('utf-8', errors='ignore')
                            status_code = resp_first_line.split(' ')[1]
                            print(f"[LOG] {full_url} - {status_code}")
                        except IndexError:
                            print(f"[LOG] {full_url} - Unknown Status")
                        first_chunk = False

                    client_socket.sendall(data)
                elif sock is client_socket:
                    server_socket.sendall(data)

            if not sockets or server_socket not in sockets or client_socket not in sockets:
                break

    except Exception as e:
        pass
    finally:
        client_socket.close()
        try:
            server_socket.close()
        except:
            pass


def start_proxy():
    blacklist = load_blacklist()
    print(f"Прокси-сервер запущен на {HOST}:{PORT}")
    print(f"Загружено доменов в черный список: {len(blacklist)}")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(100)

    try:
        while True:
            client_socket, client_address = server.accept()

            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address, blacklist)
            )
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\n!Остановка прокси-сервера")
    finally:
        server.close()


if __name__ == '__main__':
    start_proxy()
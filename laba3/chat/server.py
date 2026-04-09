import socket
import threading

clients = []
names = {}

def broadcast(message, sender=None):
    for client in clients:
        if client != sender:
            try:
                client.send(message.encode())
            except:
                clients.remove(client)

def handle_client(client):
    try:
        name = client.recv(1024).decode()
        names[client] = name

        broadcast(f"{name} подключился к чату")

        while True:
            message = client.recv(1024).decode()
            if not message:
                break

            formatted = f"[{name}]: {message}"
            print(formatted)
            broadcast(formatted, client)

    except:
        pass

    finally:
        name = names.get(client, "Unknown")
        print(f"{name} отключился")

        clients.remove(client)
        del names[client]
        broadcast(f"{name} покинул чат")
        client.close()

def start_server():
    host = input("Введите IP: ")
    port = int(input("Введите порт: "))

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        server.bind((host, port))
    except OSError:
        print("Порт занят!")
        return

    server.listen()
    print(f"Сервер запущен на {host}:{port}")

    while True:
        client, addr = server.accept()
        print(f"Подключение: {addr}")

        clients.append(client)

        thread = threading.Thread(target=handle_client, args=(client,))
        thread.start()

if __name__ == "__main__":
    start_server()
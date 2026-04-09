import socket
import threading
import sys


def receive_messages(client):
    while True:
        try:
            message = client.recv(1024).decode()
            if message:
                print("\n" + message)
                print("[Вы]: ", end="", flush=True)
        except:
            print("\nПотеряно соединение")
            client.close()
            break


def send_messages(client):
    while True:
        msg = input("[Вы]: ")
        if msg.lower() == "exit":
            client.close()
            sys.exit()
        client.send(msg.encode())


def start_client():
    host = input("IP сервера (куда подключаемся): ")
    port = int(input("Порт сервера: "))

    my_ip = input("Введите ваш исходящий IP (например, 127.0.0.2): ")
    name = input("Ваше имя: ")

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    client.bind((my_ip, 0))

    client.connect((host, port))
    client.send(name.encode())

    print(f"\nДобро пожаловать, {name}!")
    print(f"Вы сидите с адреса: {my_ip}")
    print("Введите 'exit' для выхода\n")

    threading.Thread(target=receive_messages, args=(client,), daemon=True).start()
    send_messages(client)


if __name__ == "__main__":
    start_client()
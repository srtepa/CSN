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
    host = input("IP сервера: ")
    port = int(input("Порт: "))
    name = input("Ваше имя: ")

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))

    client.send(name.encode())

    print(f"\nДобро пожаловать, {name}!")
    print("Введите 'exit' для выхода\n")

    threading.Thread(target=receive_messages, args=(client,), daemon=True).start()
    threading.Thread(target=send_messages, args=(client,), daemon=True).start()

    while True:
        pass

if __name__ == "__main__":
    start_client()
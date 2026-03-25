import socket
import struct
import time
import os
import argparse
import sys

def calculate_checksum(data):
    if len(data) % 2 == 1:
        data += b'\0'#добавляем нулевой байт

    checksum = 0
    for i in range(0, len(data), 2):
        word = data[i] + (data[i + 1] << 8)
        checksum += word
        checksum = (checksum & 0xffffffff)

    checksum = (checksum >> 16) + (checksum & 0xffff)#складываем старшие и младшие 16 бит
    checksum += (checksum >> 16)

    return ~checksum & 0xffff


def create_icmp_echo_request(packet_id, seq_number):
    header = struct.pack('!bbHHh', 8, 0, 0, packet_id, seq_number)

    data = struct.pack('d', time.time()) + b'MyTracerouteTest'

    my_checksum = calculate_checksum(header + data)

    header = struct.pack('!bbHHh', 8, 0, socket.htons(my_checksum), packet_id, seq_number)#пересобираем заголовок с правильной контрольной суммой

    return header + data


def get_hostname(ip, resolve):#доп. задание
    if not resolve:
        return ip
    try:
        host, _, _ = socket.gethostbyaddr(ip)
        return f"{host} ({ip})"
    except socket.herror:
        return ip


def traceroute(target_host, resolve_dns=False, max_hops=30, timeout=2.0):
    try:
        dest_ip = socket.gethostbyname(target_host)#прямой DNS
    except socket.gaierror:
        print(f"Не удалось разрешить имя узла: {target_host}")
        sys.exit(1)

    print(f"Трассировка маршрута к {target_host} [{dest_ip}], максимальное число прыжков {max_hops}:")

    packet_id = os.getpid() & 0xFFFF
    seq_number = 1

    for ttl in range(1, max_hops + 1):
        rtts = []
        hop_address = None
        icmp_type = None

        for _ in range(3):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            except PermissionError:
                print("Ошибка: Для использования сырых сокетов требуются права root. Запустите через sudo.")
                sys.exit(1)

            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
            sock.settimeout(timeout)

            packet = create_icmp_echo_request(packet_id, seq_number)

            send_time = time.time()

            sock.sendto(packet, (dest_ip, 1))

            try:
                data, addr = sock.recvfrom(1024)
                recv_time = time.time()

                hop_address = addr[0]

                ip_header_length = (data[0] & 0x0F) * 4

                icmp_type = data[ip_header_length]

                rtt = round((recv_time - send_time) * 1000, 2)
                rtts.append(f"{rtt} ms")

            except socket.timeout:
                rtts.append("*")
            finally:
                sock.close()
                seq_number += 1

        #собираем и выводим строку для текущего прыжка (hop)
        rtt_str = "  ".join(f"{r:>8}" for r in rtts)
        if hop_address:
            display_name = get_hostname(hop_address, resolve_dns)
            print(f"{ttl:>3}  {rtt_str}  {display_name}")
        else:
            print(f"{ttl:>3}  {rtt_str}  Превышен интервал ожидания для запроса.")

        #дошли до узла
        if icmp_type == 0 and hop_address == dest_ip:
            print("\nТрассировка завершена.")
            break


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="My custom Traceroute (ICMP based)")
    parser.add_argument("host", help="IP адрес или доменное имя целевого узла")
    parser.add_argument("-r", "--resolve", action="store_true",
                        help="Разрешать IP адреса в доменные имена (reverse DNS)")

    args = parser.parse_args()

    traceroute(args.host, resolve_dns=args.resolve)
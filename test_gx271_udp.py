import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', 50184))
sock.settimeout(10)
#sock.connect(('192.168.1.3', 50184))


data = sock.recvfrom(1500)

print(data)

sock.close()
import socket
import select

# this allows accepting UDP packets from 50184 even though the GEARS application is also listening there

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('',50184))
sock.setblocking(0)

for _ in range(10):
    result = select.select([sock],[],[])
    msg = result[0][0].recv(1500) 
    print (msg)

sock.close()
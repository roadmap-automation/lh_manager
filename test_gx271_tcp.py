import socket
import xml.etree.ElementTree as ET

REMOTE_HOST = "192.168.1.3"
def recvall(sock):
    BUFF_SIZE = 4096 # 4 KiB
    data = b''
    while True:
        part = sock.recv(BUFF_SIZE)
        data += part
        if len(part) < BUFF_SIZE:
            # either 0 or end of data
            break
    return data

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect((REMOTE_HOST, 50185))

msg = '<Gilson><GilsonConnect>python</GilsonConnect></Gilson>'

#msg = '<Gilson>​<CommandData>​<Command>​<CommandInfo>​<InstrumentInfo>​<DeviceName>GX-271</DeviceName>​<DeviceId>15</DeviceId>​</InstrumentInfo>​<SequenceNumber>6</#SequenceNumber>​<Synchronize>True</Synchronize>​<CommandXML>​<CommandName>Output Contacts</CommandName>​<Parameters>​<Parameter>​<ParameterName>Output 1</#ParameterName>​<ParameterValue>On</ParameterValue>​</Parameter>​<Parameter>​<ParameterName>Output 2</ParameterName>​<ParameterValue>Off</ParameterValue>​</Parameter>​</#Parameters>​</CommandXML>​</CommandInfo>​</Command>​</CommandData>​</Gilson>​'
sock.sendall(msg.encode())
data = sock.recv(10240)
print(data.decode())
xdata = ET.fromstring(data.decode())
par_resp = dict([(k.text, v.text) for k, v in zip(xdata.iter('ParameterName'), xdata.iter('ParameterValue'))])
#print(xdata.tag, xdata.attrib, [(k.text, v.text) for k, v in zip(xdata.iter('ParameterName'), xdata.iter('ParameterValue'))])

sock.close()

newport = int(par_resp['ResponseValue'])
print(newport)

if True:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect((REMOTE_HOST, newport))
    msg = '<Gilson>​<CommandData>​<Command>​<CommandInfo>​<InstrumentInfo>​<DeviceName>GX-271</DeviceName>​<DeviceId>35</DeviceId>​</InstrumentInfo>​<SequenceNumber>6</SequenceNumber>​<Synchronize>True</Synchronize>​<CommandXML>​<CommandName>Output Contacts</CommandName>​<Parameters>​<Parameter>​<ParameterName>Output 1</ParameterName>​<ParameterValue>On</ParameterValue>​</Parameter>​<Parameter>​<ParameterName>Output 2</ParameterName>​<ParameterValue>Off</ParameterValue>​</Parameter>​</Parameters>​</CommandXML>​</CommandInfo>​</Command>​</CommandData>​</Gilson>​'
    #msg = '<Gilson>​<CommandData>​<Command>​<CommandInfo>​<InstrumentInfo>​<DeviceName>GX-271</DeviceName>​<DeviceId>15</DeviceId>​</InstrumentInfo>​<SequenceNumber>6</SequenceNumber>​<Synchronize>True</Synchronize>​<CommandXML>​<CommandName>Get Error</CommandName>​</CommandXML>​</CommandInfo>​</Command>​</CommandData>​</Gilson>​'
    #msg = '<Gilson></Gilson>'
    msg = '<Gilson><CommandData><Commands><Command><CommandType>Local</CommandType><CommandInfo><InstrumentInfo><DeviceName>GX-27x</DeviceName><DeviceId>35</DeviceId></InstrumentInfo><SequenceNumber>2</SequenceNumber><Synchronize>True</Synchronize><Selected>False</Selected><CommandXML><CommandName>Get XY Position</CommandName></CommandXML></CommandInfo></Command></Commands></CommandData></Gilson>'
    sock.sendall(msg.encode())
    for _ in range(10):
        try:
            data = recvall(sock)
            print("Response>" in data.decode())
        except socket.timeout:
            break
        #print(data.decode())
    #data += recvall(sock)
    ##data += recvall(sock)
    #data += recvall(sock)
    #data += recvall(sock)

    
    print(data.decode())
    sock.close()
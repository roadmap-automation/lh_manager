import sys
import time
import socket
import xml.etree.ElementTree as ET

import clr
clr.AddReference("GilsonEthernet")
clr.AddReference("System.Net.NetworkInformation")
import GilsonEthernet
import System.Net.NetworkInformation

print_beacon = True

socketList = GilsonEthernet.GilsonTcpList()

def onSocketClosed(ipaddress):
    
    socketList.Remove(socketList[ipaddress])

def onSocketConnected(ipaddress):
    
    print('Connected!')

def datahandler(data):
    if data is not None:
        print(data.Data)
        print(type(data))
    else:
        print('None!')

    return True

def beacon_datahandler(data):
    if print_beacon:
        if data is not None:
            print(data.Data)
            for i in data:
                print(i.InstructionSetName)
            print('-----')

def AddNewSocket(ipaddress, name='hello', instrumentGuid=None):

    if instrumentGuid is not None:
        # syringe pumps
        port = GilsonEthernet.EthernetSend().RequestPort(ipaddress, name, instrumentGuid)
    else:
        port = GilsonEthernet.EthernetSend().RequestPort(ipaddress, name)
    
    print(port)

    if port != -1:

        tcp = GilsonEthernet.GilsonTcp(System.Net.IPAddress.Parse(ipaddress), port)
        tcp.OnSocketClosed = GilsonEthernet.SocketIPDelegate(onSocketClosed)
        tcp.OnSocketConnected = GilsonEthernet.SocketIPDelegate(onSocketConnected)
        tcp.AddListener(GilsonEthernet.EthernetDataDelegate(datahandler))
        socketList.Add(tcp)

    else:
        print('No port given')

# use to look at beacon signals from available instruments
if 1:
    beaconListener = GilsonEthernet.EthernetUDPListener(GilsonEthernet.EthernetDataDelegate(beacon_datahandler), GilsonEthernet.GilsonPorts.BeaconPort)
    beaconListener.Start()
    time.sleep(4)   # give time for beacons to be sent

# Syringe pumps; #guid must be read off of beacon signal (do manually for now)
ipaddress, guid = '192.168.1.2', '2e4485f7-b0ec-4e61-845c-d532c4bb8ab0'

# GX-271
#ipaddress, guid = '192.168.1.3', None
sequence_number = 10
timeout = 3

AddNewSocket(ipaddress, name='hello', instrumentGuid=guid)
print(socketList[0].get_IsConnected())
time.sleep(1)


#em = GilsonEthernet.EthernetMessage()
#ec = GilsonEthernet.EthernetCommand(GilsonEthernet.EthernetMessages.CommandGetInstructionSet, 'Verity 4120 Syringe Pump', 11, True)
#ec = GilsonEthernet.EthernetCommand('Get Serial Number', 'Verity 4120 Syringe Pump', None, False, 5)
#em.Commands.Add(ec)

#socketList[0].TcpSend(em)

#time.sleep(10)

if 1:
    print_beacon = False
 
    em = GilsonEthernet.EthernetMessage()
    #ec = GilsonEthernet.EthernetCommand(GilsonEthernet.EthernetMessages.CommandGetFirmwareVersion, 'Verity 4120 Syringe Pump', guid, False)
    ec = GilsonEthernet.EthernetCommand("Get Motor Status", "Verity 4120 Syringe Pump", -1, True)
    #ec = GilsonEthernet.EthernetCommand('Get Serial Number', 'Verity 4120 Syringe Pump', None, False, 5)
    em.Commands.Add(ec)

    time.sleep(1)
    tcp = socketList[0]
    erb = tcp.TcpSendAndWait(em, 3)
    #print(erb)

    tcp.Disconnect()
#tcp.Disconnect()



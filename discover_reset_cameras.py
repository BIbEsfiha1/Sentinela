import socket
import struct
import json
import time

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

LOCAL_IP = get_local_ip()
print(f"Local IP: {LOCAL_IP}")

# XMEye Discovery Protocol (Port 34567)
# Header: 0xff + 0x00 + 0x00 + 0x00 + len(data)
def discover_xmeye():
    print("\n--- Scanning for XMEye/Intelbras cameras (UDP 34567) ---")
    
    # Discovery Command (cmd=1000)
    # This structure is simplified; usually configManager.cgi or raw bytes are used.
    # But XMEye devices listen for a specific broadcast.
    # Using a common discovery payload found in open source tools for XMEye
    
    # Constructing a valid XMEye discovery packet is tricky without full spec.
    # However, many respond to an empty or specific JSON in the payload.
    # Let's try a proven payload for "Search" (cmd 1000)
    
    # Payload for "NetWork.NetCommon" search?
    # Actually, simpler: send a broadcast and listen.
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(2)
    sock.bind(("", 0)) # Bind to any random port
    
    # Official XMEye discovery packet structure (roughly):
    # Head: 0xfa, 0x0b, 0x00, 0x00 (magic)
    # ....
    # Let's try sending a generic JSON probe which some firmwares accept
    msg = json.dumps({"Cmd": "Search", "Token": "123"}).encode()
    
    # But the binary protocol is standard.
    # Let's try the binary probe used by 'python-dvr' and similar libs
    # Ret = 0xf4 (Search)
    # Session = 0
    # Sequence = 0
    DISCOVERY_PORT = 34567
    
    # Packet: [Head 4B] + [Cmd 2B] + [Len 2B] + [Session 4B] + [Seq 4B] + [Data...]
    # Head: 0xff 0x00 0x00 0x00
    # Cmd: 1000 (0x03e8) -> Discovery
    # Len: 0
    
    packet = struct.pack("IHHII", 0x000000ff, 1000, 0, 0, 0)
    
    # Broadcast to 255.255.255.255 and local subnet broadcast
    targets = ["<broadcast>", "255.255.255.255"]
    if LOCAL_IP != "0.0.0.0":
        prefix = ".".join(LOCAL_IP.split(".")[:3])
        targets.append(f"{prefix}.255")

    found = []

    for t in targets:
        try:
            sock.sendto(packet, (t, 34567))
        except Exception as e:
            # print(f"Send to {t} failed: {e}")
            pass

    start = time.time()
    while time.time() - start < 4:
        try:
            data, addr = sock.recvfrom(1024)
            # data structure: [Head 4] [Cmd 2] [Len 2] ... JSON
            if len(data) > 16:
                # Parse header
                head, cmd, length, session, seq = struct.unpack("IHHII", data[:16])
                json_data = data[16:].decode(errors='ignore').strip('\x00')
                try:
                    info = json.loads(json_data)
                    print(f"FOUND XMEye DEVICE at {addr[0]}:")
                    print(json.dumps(info, indent=2))
                    found.append((addr[0], info))
                except:
                    print(f"Received raw bytes from {addr[0]}: {json_data}")
        except socket.timeout:
            pass
        except Exception as e:
            print(f"Error receiving: {e}")

    return found

# ONVIF Discovery (UDP 3702)
def discover_onvif():
    print("\n--- Scanning for ONVIF devices (UDP 3702) ---")
    msg = \
    '''<?xml version="1.0" encoding="UTF-8"?>
    <e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
                xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
                xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
                xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
        <e:Header>
            <w:MessageID>uuid:{uuid}</w:MessageID>
            <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
            <w:Action a:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
        </e:Header>
        <e:Body>
            <d:Probe>
                <d:Types>dn:NetworkVideoTransmitter</d:Types>
            </d:Probe>
        </e:Body>
    </e:Envelope>'''
    
    import uuid
    msg = msg.format(uuid=uuid.uuid4())
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(2)
    sock.bind(("", 0))
    
    targets = ["239.255.255.250"] # ONVIF multicast group
    
    found = []

    for t in targets:
        try:
            sock.sendto(msg.encode(), (t, 3702))
        except:
            pass
            
    start = time.time()
    while time.time() - start < 4:
        try:
            data, addr = sock.recvfrom(4096)
            s_data = data.decode(errors='ignore')
            if "NetworkVideoTransmitter" in s_data:
                # Extract XAddrs (URL)
                import re
                urls = re.findall(r'http://\d+\.\d+\.\d+\.\d+[:\d]*/\S+', s_data)
                print(f"FOUND ONVIF DEVICE at {addr[0]}: {urls}")
                found.append(addr[0])
        except socket.timeout:
            pass
    
    return found


def main():
    xmeye = discover_xmeye()
    onvif = discover_onvif()
    
    print("\nSUMMARY:")
    if not xmeye and not onvif:
        print("No devices found via broadcast protocols.")
        print("POSSIBLE CAUSES:")
        print("1. Cameras are strictly Wi-Fi and not connected to AP yet.")
        print("2. Cameras are wired but on a vastly different subnet that blocks broadcast.")
        print("3. Firewall is blocking UDP ports 34567/3702.")
    else:
        print(f"Found {len(xmeye)} XMEye devices and {len(onvif)} ONVIF devices.")

if __name__ == "__main__":
    main()

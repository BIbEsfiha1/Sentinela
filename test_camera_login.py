"""Try to login to XMEye/Intelbras camera via HTTP API."""
import urllib.request
import json
import hashlib

IP = "192.168.15.58"

PASSWORDS = [
    "", "admin", "12345", "123456", "1234", "12345678", "123456789",
    "admin123", "admin1234", "888888", "666666", "111111", "000000",
    "tlJwpbo6", "xmhdipc", "juantech", "OxhlwSG8", "S2fGqNFs",
    "HI2105CHIP", "password", "pass", "1111", "4321", "abc123",
    "Aa123456", "Aa12345678", "Admin123", "1234qwer", "qwer1234",
    "default", "meinsm", "ftp", "supervisor",
]

def xm_hash(pw):
    """XMEye password hash."""
    md5 = hashlib.md5(pw.encode()).digest()
    chars = []
    for i in range(0, 16, 2):
        b = (md5[i] + md5[i+1]) % 0x3e
        if b < 10:
            chars.append(chr(0x30 + b))
        elif b < 36:
            chars.append(chr(0x41 + b - 10))
        else:
            chars.append(chr(0x61 + b - 36))
    return "".join(chars)


def try_login(ip, user, pw):
    """Try XMEye HTTP login."""
    login_data = json.dumps({
        "EncryptType": "MD5",
        "LoginType": "DVRIP-Web",
        "PassWord": xm_hash(pw),
        "UserName": user,
    }).encode()

    for endpoint in ["/Login", "/login"]:
        try:
            req = urllib.request.Request(
                f"http://{ip}{endpoint}",
                data=login_data,
                headers={"Content-Type": "application/json"},
            )
            try:
                resp = urllib.request.urlopen(req, timeout=3)
                body = resp.read(500).decode()
            except urllib.error.HTTPError as e:
                body = e.read(500).decode() if e.fp else ""
            
            if not body:
                continue
                
            data = json.loads(body)
            ret = data.get("Ret", -1)
            
            if ret == 100:
                session = data.get("SessionID", "?")
                print(f"*** SUCCESS! user={user} password={pw}")
                print(f"    SessionID: {session}")
                print(f"    Full response: {body}")
                return True
            elif ret == 205:
                pass  # Wrong password
            elif ret == 203:
                print(f"  user={user} pw={pw} -> Ret 203 (user not found)")
            elif ret != -1:
                print(f"  user={user} pw={pw} -> Ret {ret}: {body[:100]}")
        except Exception:
            pass
    
    return False


print(f"Testing XMEye login on {IP}...")
print(f"Trying {len(PASSWORDS)} passwords...")

found = False
for user in ["admin", "888888", "666666", "default", "user"]:
    for pw in PASSWORDS:
        if try_login(IP, user, pw):
            found = True
            break
    if found:
        break

if not found:
    print("\nNo valid credentials found.")
    print("The camera has a custom password set.")
    print("You can reset it via:")
    print("  1. The iCSee / XMEye mobile app")
    print("  2. Physical reset button on the camera")
    print("  3. Contacting Intelbras support")

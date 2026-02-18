import asyncio
from bleak import BleakScanner

async def scan_cameras():
    print("Iniciando escaneamento Bluetooth para encontrar cameras...")
    print("Certifique-se que o Bluetooth do seu computador esta LIGADO.")
    
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
    
    found = False
    print(f"\nDispositivos encontrados: {len(devices)}")
    
    for d, adv in devices.values():
        name = d.name or "Unknown"
        rssi = adv.rssi
        
        # Filtros comuns para cameras iCSee/XM
        is_camera = False
        potential_names = ["IPC", "Robot", "Smart", "Camera", "XMEye", "ICSee", "F0", "H0"]
        
        # Verifica se o nome contem termos comuns
        if any(x in name for x in potential_names) or name.startswith("IPC"):
            is_camera = True
            
        # Verifica UUIDs de servico conhecidos (se houver)
        service_uuids = adv.service_uuids
        
        if is_camera or rssi > -70: # Mostra cameras ou sinais fortes
            print(f"DEVICE: {d.address} | Name: {name} | RSSI: {rssi}")
            if service_uuids:
                print(f"  Services: {service_uuids}")
            found = True
            
    if not found:
        print("\nNenhuma camera obvia encontrada. Tente aproximar o computador.")
    else:
        print("\nSe algum desses dispositivos for sua camera, anote o endereco/nome.")

if __name__ == "__main__":
    asyncio.run(scan_cameras())

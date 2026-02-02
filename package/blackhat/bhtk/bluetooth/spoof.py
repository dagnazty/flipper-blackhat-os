#!/usr/bin/env python3
"""Bluetooth Spoofing Tools"""

import subprocess
import random
from ..utils.colors import Colors
from ..utils.interfaces import get_bt_interfaces
from ..utils.logger import Logger


def change_bt_name(name, interface='hci0'):
    """Change Bluetooth adapter name"""
    try:
        subprocess.run(['hciconfig', interface, 'name', name], check=True)
        print(Colors.success(f"Bluetooth name changed to: {name}"))
        return True
    except subprocess.CalledProcessError:
        print(Colors.error("Failed to change Bluetooth name"))
        return False
    except FileNotFoundError:
        print(Colors.error("hciconfig not found"))
        return False


def change_bt_class(device_class, interface='hci0'):
    """
    Change Bluetooth device class
    
    Common classes:
        0x5a020c - Smartphone
        0x3e0100 - Computer/Laptop
        0x240404 - Headphones
        0x200408 - Car handsfree
    """
    try:
        subprocess.run(['hciconfig', interface, 'class', device_class], check=True)
        print(Colors.success(f"Bluetooth class changed to: {device_class}"))
        return True
    except subprocess.CalledProcessError:
        print(Colors.error("Failed to change Bluetooth class"))
        return False


def generate_random_mac():
    """Generate a random Bluetooth MAC address"""
    # Keep vendor prefix area somewhat realistic
    mac = [random.randint(0, 255) for _ in range(6)]
    return ':'.join(f'{b:02X}' for b in mac)


def spoof_mac(mac, interface='hci0'):
    """
    Spoof Bluetooth MAC address
    Note: This requires bdaddr tool and may not work on all adapters
    """
    print(Colors.warning("⚠️  MAC spoofing requires bdaddr and compatible hardware"))
    
    try:
        # Bring interface down
        subprocess.run(['hciconfig', interface, 'down'], check=True)
        
        # Change MAC using bdaddr
        subprocess.run(['bdaddr', '-i', interface, mac], check=True)
        
        # Bring interface back up
        subprocess.run(['hciconfig', interface, 'up'], check=True)
        
        print(Colors.success(f"Bluetooth MAC changed to: {mac}"))
        return True
        
    except FileNotFoundError:
        print(Colors.error("bdaddr not found. Install bluez-utils or use spooftooph."))
        return False
    except subprocess.CalledProcessError as e:
        print(Colors.error(f"Failed to spoof MAC: {e}"))
        return False


def run(interface='hci0', name=None, mac=None, device_class=None):
    """Run spoofing with given parameters"""
    results = []
    
    if name:
        results.append(('Name', change_bt_name(name, interface)))
    
    if device_class:
        results.append(('Class', change_bt_class(device_class, interface)))
    
    if mac:
        results.append(('MAC', spoof_mac(mac, interface)))
    
    return results


def interactive():
    """Interactive Bluetooth spoofing"""
    logger = Logger("bt_spoof")
    
    interfaces = get_bt_interfaces()
    if not interfaces:
        print(Colors.error("No Bluetooth interfaces found"))
        return
    
    interface = interfaces[0]
    print(Colors.info(f"Using interface: {interface}"))
    
    print("\nSpoof options:")
    print("  [1] Change device name")
    print("  [2] Change device class")
    print("  [3] Spoof MAC address (requires bdaddr)")
    print("  [4] Full spoof (all of the above)")
    
    choice = input(Colors.prompt("Choice: ")).strip()
    
    if choice == '1':
        name = input(Colors.prompt("New device name: ")).strip()
        if name:
            logger.info(f"BT name spoof: {name}")
            change_bt_name(name, interface)
    
    elif choice == '2':
        print("\nCommon classes:")
        print("  [1] Smartphone (0x5a020c)")
        print("  [2] Computer (0x3e0100)")
        print("  [3] Headphones (0x240404)")
        print("  [4] Car kit (0x200408)")
        print("  [5] Custom")
        
        class_choice = input(Colors.prompt("Class: ")).strip()
        classes = {
            '1': '0x5a020c',
            '2': '0x3e0100',
            '3': '0x240404',
            '4': '0x200408'
        }
        
        if class_choice == '5':
            device_class = input(Colors.prompt("Custom class (hex): ")).strip()
        else:
            device_class = classes.get(class_choice, '0x5a020c')
        
        logger.info(f"BT class spoof: {device_class}")
        change_bt_class(device_class, interface)
    
    elif choice == '3':
        print("\nMAC options:")
        print("  [1] Random MAC")
        print("  [2] Custom MAC")
        
        mac_choice = input(Colors.prompt("Choice [1]: ")).strip() or '1'
        
        if mac_choice == '1':
            mac = generate_random_mac()
        else:
            mac = input(Colors.prompt("MAC address: ")).strip()
        
        print(Colors.warning(f"Will change MAC to: {mac}"))
        confirm = input(Colors.prompt("Proceed? [y/N]: ")).strip().lower()
        
        if confirm == 'y':
            logger.info(f"BT MAC spoof: {mac}")
            spoof_mac(mac, interface)
    
    elif choice == '4':
        name = input(Colors.prompt("Device name [iPhone]: ")).strip() or "iPhone"
        device_class = '0x5a020c'  # Smartphone
        mac = generate_random_mac()
        
        logger.info(f"Full BT spoof: name={name}, class={device_class}, mac={mac}")
        run(interface, name, mac, device_class)

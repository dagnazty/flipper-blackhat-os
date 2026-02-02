#!/usr/bin/env python3
"""Automated Attack Workflows"""

import time
from ..utils.colors import Colors
from ..utils.logger import Logger
from ..utils.interfaces import get_wifi_interfaces, get_bt_interfaces, enable_monitor_mode, disable_monitor_mode


def wifi_audit():
    """
    Full WiFi security audit workflow:
    1. Scan for networks
    2. Identify targets
    3. Capture handshakes
    4. Attempt crack (if wordlist available)
    """
    logger = Logger("wifi_audit")
    
    print(Colors.info("=== WiFi Security Audit ==="))
    print(Colors.warning("⚠️  Only audit networks you own or have permission to test!\n"))
    
    from ..wifi import scanner, handshake
    
    # Step 1: Get interface
    interfaces = get_wifi_interfaces()
    if not interfaces:
        print(Colors.error("No WiFi interfaces found"))
        return
    
    interface = interfaces[0]
    print(Colors.info(f"Using interface: {interface}"))
    
    # Step 2: Scan networks
    print(Colors.info("\n[1/4] Scanning for networks..."))
    networks = scanner.scan(interface)
    
    if not networks:
        print(Colors.warning("No networks found"))
        return
    
    scanner.display_networks(networks)
    
    # Step 3: Select target
    print(Colors.info("\n[2/4] Select target network:"))
    for i, net in enumerate(networks[:10], 1):
        print(f"  [{i}] {net.get('ssid', '<hidden>')} ({net.get('bssid')}) - {net.get('encryption')}")
    
    try:
        choice = int(input(Colors.prompt("Target number: ")))
        target = networks[choice - 1]
    except (ValueError, IndexError):
        print(Colors.error("Invalid selection"))
        return
    
    logger.info(f"Target: {target.get('ssid')} ({target.get('bssid')})")
    
    # Step 4: Capture handshake
    print(Colors.info(f"\n[3/4] Capturing handshake for {target.get('ssid')}..."))
    
    if not enable_monitor_mode(interface):
        print(Colors.error("Failed to enable monitor mode"))
        return
    
    try:
        cap_file = handshake.capture(
            interface, 
            target.get('bssid'),
            target.get('channel', '1')
        )
        
        if cap_file:
            logger.success(f"Handshake captured: {cap_file}")
            print(Colors.info("\n[4/4] Audit complete!"))
            print(Colors.success(f"Handshake saved to: {cap_file}"))
            print(Colors.info("Use aircrack-ng or hashcat to attempt password recovery"))
        else:
            print(Colors.warning("No handshake captured"))
            
    finally:
        disable_monitor_mode(interface)


def network_discovery():
    """
    Network discovery workflow:
    1. Identify local network
    2. Scan for hosts
    3. Port scan discovered hosts
    4. Service detection
    """
    logger = Logger("network_discovery")
    
    print(Colors.info("=== Network Discovery ===\n"))
    
    import subprocess
    from ..network import portscan
    from ..recon import services
    
    # Step 1: Get local network info
    print(Colors.info("[1/4] Identifying local network..."))
    
    try:
        result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'src' in line and 'default' not in line:
                parts = line.split()
                network = parts[0]
                print(Colors.success(f"Local network: {network}"))
                break
        else:
            network = input(Colors.prompt("Enter network range (e.g., 192.168.1.0/24): "))
    except:
        network = input(Colors.prompt("Enter network range (e.g., 192.168.1.0/24): "))
    
    logger.info(f"Scanning network: {network}")
    
    # Step 2: Host discovery
    print(Colors.info("\n[2/4] Discovering hosts..."))
    
    hosts = []
    try:
        result = subprocess.run(
            ['nmap', '-sn', '-n', network],
            capture_output=True, text=True, timeout=120
        )
        
        for line in result.stdout.split('\n'):
            if 'Nmap scan report for' in line:
                ip = line.split()[-1]
                hosts.append(ip)
                print(Colors.success(f"Host found: {ip}"))
                
    except Exception as e:
        print(Colors.error(f"Host discovery failed: {e}"))
        return
    
    if not hosts:
        print(Colors.warning("No hosts found"))
        return
    
    print(Colors.info(f"Found {len(hosts)} hosts"))
    
    # Step 3: Quick port scan
    print(Colors.info("\n[3/4] Quick port scan..."))
    
    for host in hosts[:5]:  # Limit to first 5 hosts
        print(Colors.info(f"\nScanning {host}:"))
        portscan.scan(host, "22,80,443,3389,8080", "nmap")
    
    # Step 4: Service detection on interesting hosts
    print(Colors.info("\n[4/4] Discovery complete!"))
    logger.success(f"Discovered {len(hosts)} hosts")
    
    print(Colors.info(f"\nRun 'bhtk recon services' for detailed service detection"))


def quick_recon():
    """
    Quick reconnaissance workflow:
    1. DNS lookup
    2. Port scan
    3. Banner grab
    4. Subdomain enumeration
    """
    logger = Logger("quick_recon")
    
    print(Colors.info("=== Quick Recon ===\n"))
    
    import socket
    from ..recon import banner, services, subdomain
    
    target = input(Colors.prompt("Target (IP or domain): ")).strip()
    if not target:
        print(Colors.error("Target required"))
        return
    
    logger.info(f"Quick recon: {target}")
    
    # Step 1: DNS lookup
    print(Colors.info("\n[1/4] DNS Resolution..."))
    
    try:
        ip = socket.gethostbyname(target)
        print(Colors.success(f"Resolved: {target} -> {ip}"))
        
        # Reverse DNS
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            print(Colors.success(f"Reverse DNS: {ip} -> {hostname}"))
        except:
            pass
    except socket.gaierror:
        print(Colors.warning(f"Could not resolve {target}"))
        ip = target  # Assume it's already an IP
    
    # Step 2: Quick port scan
    print(Colors.info("\n[2/4] Quick Port Scan..."))
    from ..network.portscan import quick_scan
    quick_scan(ip)
    
    # Step 3: Banner grab
    print(Colors.info("\n[3/4] Banner Grabbing..."))
    banners = banner.grab(ip)
    
    # Step 4: Subdomain enum (if domain)
    if not target.replace('.', '').isdigit():  # Not an IP
        print(Colors.info("\n[4/4] Subdomain Enumeration (quick)..."))
        subdomain.find(target, COMMON_SUBDOMAINS[:20])  # Just first 20
    else:
        print(Colors.info("\n[4/4] Skipping subdomain enum (target is IP)"))
    
    print(Colors.success("\nQuick recon complete!"))
    logger.success("Recon completed")


# Import for subdomain wordlist
from ..recon.subdomain import COMMON_SUBDOMAINS

#!/usr/bin/env python3
"""WiFi Network Scanner"""

import subprocess
import re
import time
from ..utils.colors import Colors
from ..utils.interfaces import get_wifi_interfaces, select_interface, enable_monitor_mode
from ..utils.logger import Logger


def scan(interface=None):
    """Scan for WiFi networks using iw"""
    if not interface:
        interfaces = get_wifi_interfaces()
        interface = select_interface(interfaces, "WiFi")
    
    if not interface:
        return []
    
    print(Colors.info(f"Scanning on {interface}..."))
    
    networks = []
    try:
        # Use iw to scan
        result = subprocess.run(
            ['iw', interface, 'scan'],
            capture_output=True, text=True, timeout=30
        )
        
        # Parse results
        current = {}
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('BSS '):
                if current:
                    networks.append(current)
                bssid = line.split()[1].replace('(', '').replace(')', '')
                current = {'bssid': bssid, 'ssid': '', 'channel': '', 'signal': '', 'encryption': 'Open'}
            elif 'SSID:' in line:
                current['ssid'] = line.split('SSID:')[-1].strip()
            elif 'signal:' in line:
                current['signal'] = line.split('signal:')[-1].strip()
            elif 'primary channel:' in line:
                current['channel'] = line.split(':')[-1].strip()
            elif 'WPA' in line or 'RSN' in line:
                current['encryption'] = 'WPA/WPA2'
            elif 'WEP' in line:
                current['encryption'] = 'WEP'
        
        if current:
            networks.append(current)
            
    except subprocess.TimeoutExpired:
        print(Colors.error("Scan timed out"))
    except Exception as e:
        print(Colors.error(f"Scan failed: {e}"))
    
    return networks


def display_networks(networks):
    """Display scanned networks in a table"""
    if not networks:
        print(Colors.warning("No networks found"))
        return
    
    print(f"\n{Colors.CYAN}{'BSSID':<20} {'SSID':<25} {'CH':<4} {'Signal':<10} {'Enc'}{Colors.RESET}")
    print("-" * 70)
    
    for net in sorted(networks, key=lambda x: x.get('signal', ''), reverse=True):
        ssid = net.get('ssid', '<hidden>')[:24] or '<hidden>'
        bssid = net.get('bssid', '')
        channel = net.get('channel', '')
        signal = net.get('signal', '')
        enc = net.get('encryption', 'Open')
        
        # Color code by encryption
        if enc == 'Open':
            color = Colors.GREEN
        elif 'WEP' in enc:
            color = Colors.YELLOW
        else:
            color = Colors.WHITE
        
        print(f"{color}{bssid:<20} {ssid:<25} {channel:<4} {signal:<10} {enc}{Colors.RESET}")
    
    print(f"\n{Colors.info(f'Found {len(networks)} networks')}")


def interactive():
    """Interactive WiFi scanner"""
    logger = Logger("wifi_scan")
    
    interfaces = get_wifi_interfaces()
    interface = select_interface(interfaces, "WiFi")
    
    if not interface:
        return
    
    print(Colors.info("Starting WiFi scan (Ctrl+C to stop)..."))
    
    try:
        networks = scan(interface)
        display_networks(networks)
        
        # Log results
        for net in networks:
            logger.raw(f"{net.get('bssid')} | {net.get('ssid')} | {net.get('encryption')}")
            
    except KeyboardInterrupt:
        print(Colors.warning("\nScan stopped"))

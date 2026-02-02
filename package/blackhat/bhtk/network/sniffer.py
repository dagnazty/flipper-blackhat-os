#!/usr/bin/env python3
"""Packet Sniffer"""

import subprocess
import os
import time
from ..utils.colors import Colors
from ..utils.logger import Logger


OUTPUT_DIR = "/var/log/bhtk/captures"


def capture(interface=None, filter_expr=None, output_file=None, count=0):
    """
    Capture packets using tcpdump
    
    Args:
        interface: Network interface
        filter_expr: BPF filter expression
        output_file: PCAP output file
        count: Number of packets (0 = continuous)
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if not output_file:
        output_file = os.path.join(OUTPUT_DIR, f"capture_{int(time.time())}.pcap")
    
    cmd = ['tcpdump']
    
    if interface:
        cmd.extend(['-i', interface])
    
    if count:
        cmd.extend(['-c', str(count)])
    
    cmd.extend(['-w', output_file])
    
    if filter_expr:
        cmd.append(filter_expr)
    
    print(Colors.info(f"Capturing packets to {output_file}"))
    print(Colors.info("Press Ctrl+C to stop"))
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(Colors.warning("\nCapture stopped"))
    
    if os.path.exists(output_file):
        size = os.path.getsize(output_file)
        print(Colors.success(f"Captured {size} bytes to {output_file}"))
        return output_file
    
    return None


def live_capture(interface=None, filter_expr=None):
    """Live packet display"""
    cmd = ['tcpdump', '-l', '-n']
    
    if interface:
        cmd.extend(['-i', interface])
    
    if filter_expr:
        cmd.append(filter_expr)
    
    print(Colors.info("Live packet capture (Ctrl+C to stop)"))
    print("-" * 60)
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(Colors.warning("\nCapture stopped"))


def interactive():
    """Interactive packet sniffer"""
    logger = Logger("sniffer")
    
    print("\nCapture mode:")
    print("  [1] Live display")
    print("  [2] Save to file")
    
    mode = input(Colors.prompt("Mode [1]: ")).strip() or "1"
    
    # Get interface
    interface = input(Colors.prompt("Interface (Enter for any): ")).strip() or None
    
    # Common filters
    print("\nFilter presets:")
    print("  [1] All traffic")
    print("  [2] HTTP only")
    print("  [3] DNS only")
    print("  [4] Credentials (FTP, Telnet, HTTP Basic)")
    print("  [5] Custom filter")
    
    filter_choice = input(Colors.prompt("Filter [1]: ")).strip() or "1"
    
    filters = {
        "1": None,
        "2": "port 80 or port 8080",
        "3": "port 53",
        "4": "port 21 or port 23 or port 80",
        "5": input(Colors.prompt("Custom BPF filter: ")).strip() if filter_choice == "5" else None
    }
    
    filter_expr = filters.get(filter_choice)
    
    logger.info(f"Sniffer: interface={interface}, filter={filter_expr}")
    
    if mode == "1":
        live_capture(interface, filter_expr)
    else:
        capture(interface, filter_expr)

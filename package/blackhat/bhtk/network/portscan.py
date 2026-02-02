#!/usr/bin/env python3
"""Port Scanner"""

import subprocess
import socket
from ..utils.colors import Colors
from ..utils.logger import Logger


def scan(target, ports="1-1000", tool="nmap"):
    """
    Scan ports on target using nmap or masscan
    
    Args:
        target: Target IP or hostname
        ports: Port range (e.g., "1-1000", "22,80,443")
        tool: "nmap" or "masscan"
    """
    if not target:
        print(Colors.error("Target required"))
        return []
    
    print(Colors.info(f"Scanning {target} ports {ports}..."))
    
    results = []
    
    if tool == "nmap":
        try:
            cmd = ['nmap', '-sS', '-Pn', '-p', ports, '--open', target]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            for line in result.stdout.split('\n'):
                if '/tcp' in line and 'open' in line:
                    parts = line.split()
                    port = parts[0].split('/')[0]
                    service = parts[2] if len(parts) > 2 else 'unknown'
                    results.append({'port': port, 'state': 'open', 'service': service})
                    print(Colors.success(f"Port {port}/tcp open - {service}"))
                    
        except subprocess.TimeoutExpired:
            print(Colors.error("Scan timed out"))
        except FileNotFoundError:
            print(Colors.error("nmap not found"))
    
    elif tool == "masscan":
        try:
            cmd = ['masscan', target, '-p', ports, '--rate=1000']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            for line in result.stdout.split('\n'):
                if 'open' in line:
                    parts = line.split()
                    for p in parts:
                        if p.isdigit():
                            results.append({'port': p, 'state': 'open', 'service': 'unknown'})
                            print(Colors.success(f"Port {p}/tcp open"))
                            break
                            
        except FileNotFoundError:
            print(Colors.error("masscan not found, falling back to nmap"))
            return scan(target, ports, "nmap")
    
    print(Colors.info(f"Found {len(results)} open ports"))
    return results


def quick_scan(target):
    """Quick scan of common ports"""
    common_ports = "21,22,23,25,53,80,110,139,443,445,3306,3389,5432,8080"
    return scan(target, common_ports)


def interactive():
    """Interactive port scanner"""
    logger = Logger("portscan")
    
    target = input(Colors.prompt("Target IP/hostname: ")).strip()
    if not target:
        print(Colors.error("Target required"))
        return
    
    print("\nScan type:")
    print("  [1] Quick scan (common ports)")
    print("  [2] Full scan (1-65535)")
    print("  [3] Custom range")
    
    choice = input(Colors.prompt("Choice [1]: ")).strip() or "1"
    
    if choice == "1":
        ports = "21,22,23,25,53,80,110,139,443,445,3306,3389,5432,8080"
    elif choice == "2":
        ports = "1-65535"
        print(Colors.warning("Full scan may take a long time..."))
    else:
        ports = input(Colors.prompt("Port range (e.g., 1-1000): ")).strip() or "1-1000"
    
    logger.info(f"Port scan: {target} ports {ports}")
    
    try:
        results = scan(target, ports)
        for r in results:
            logger.raw(f"{target}:{r['port']} - {r['service']}")
    except KeyboardInterrupt:
        print(Colors.warning("\nScan cancelled"))

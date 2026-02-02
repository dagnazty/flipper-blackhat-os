#!/usr/bin/env python3
"""Service Detection"""

import subprocess
from ..utils.colors import Colors
from ..utils.logger import Logger


def detect(target, ports="1-1000"):
    """
    Detect services using nmap service detection
    
    Args:
        target: Target IP/hostname
        ports: Port range to scan
    """
    if not target:
        print(Colors.error("Target required"))
        return []
    
    print(Colors.info(f"Detecting services on {target}..."))
    
    services = []
    
    try:
        cmd = ['nmap', '-sV', '-Pn', '-p', ports, '--open', target]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        print(f"\n{Colors.CYAN}{'Port':<10} {'State':<8} {'Service':<15} {'Version'}{Colors.RESET}")
        print("-" * 60)
        
        for line in result.stdout.split('\n'):
            if '/tcp' in line or '/udp' in line:
                parts = line.split()
                if len(parts) >= 3:
                    port = parts[0]
                    state = parts[1]
                    service = parts[2]
                    version = ' '.join(parts[3:]) if len(parts) > 3 else ''
                    
                    services.append({
                        'port': port,
                        'state': state,
                        'service': service,
                        'version': version
                    })
                    
                    print(f"{port:<10} {state:<8} {service:<15} {version}")
        
    except subprocess.TimeoutExpired:
        print(Colors.error("Service detection timed out"))
    except FileNotFoundError:
        print(Colors.error("nmap not found"))
    
    print(f"\n{Colors.info(f'Detected {len(services)} services')}")
    return services


def interactive():
    """Interactive service detection"""
    logger = Logger("services")
    
    target = input(Colors.prompt("Target IP/hostname: ")).strip()
    if not target:
        print(Colors.error("Target required"))
        return
    
    print("\nScan type:")
    print("  [1] Quick (top 100 ports)")
    print("  [2] Standard (1-1000)")
    print("  [3] Full (all 65535 ports)")
    print("  [4] Custom range")
    
    choice = input(Colors.prompt("Choice [1]: ")).strip() or "1"
    
    port_ranges = {
        "1": "1-100",
        "2": "1-1000",
        "3": "1-65535",
    }
    
    if choice == "4":
        ports = input(Colors.prompt("Port range: ")).strip()
    else:
        ports = port_ranges.get(choice, "1-100")
    
    if choice == "3":
        print(Colors.warning("Full scan will take a long time..."))
        confirm = input(Colors.prompt("Continue? [y/N]: ")).strip().lower()
        if confirm != 'y':
            return
    
    logger.info(f"Service detection: {target} ports {ports}")
    
    try:
        services = detect(target, ports)
        for svc in services:
            logger.raw(f"{target} | {svc['port']} | {svc['service']} | {svc['version']}")
    except KeyboardInterrupt:
        print(Colors.warning("\nScan cancelled"))

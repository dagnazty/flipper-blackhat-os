#!/usr/bin/env python3
"""Banner Grabbing"""

import socket
from ..utils.colors import Colors
from ..utils.logger import Logger


def grab(target, port=None, timeout=5):
    """
    Grab service banner from target
    
    Args:
        target: Target hostname/IP
        port: Port number (or list of ports)
        timeout: Connection timeout
    """
    if not target:
        print(Colors.error("Target required"))
        return {}
    
    # Default ports if not specified
    if not port:
        ports = [21, 22, 23, 25, 80, 110, 143, 443, 993, 995, 3306, 3389]
    elif isinstance(port, int):
        ports = [port]
    else:
        ports = port
    
    results = {}
    
    for p in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((target, p))
            
            # Send probe for HTTP
            if p in [80, 8080, 443]:
                sock.send(b"HEAD / HTTP/1.0\r\n\r\n")
            else:
                sock.send(b"\r\n")
            
            banner = sock.recv(1024).decode('utf-8', errors='ignore').strip()
            sock.close()
            
            if banner:
                results[p] = banner
                print(Colors.success(f"Port {p}: {banner[:80]}"))
            
        except socket.timeout:
            pass
        except ConnectionRefusedError:
            pass
        except Exception as e:
            pass
    
    return results


def interactive():
    """Interactive banner grabber"""
    logger = Logger("banner")
    
    target = input(Colors.prompt("Target hostname/IP: ")).strip()
    if not target:
        print(Colors.error("Target required"))
        return
    
    port_input = input(Colors.prompt("Port(s) [common ports]: ")).strip()
    
    if port_input:
        # Parse port input (comma-separated or range)
        ports = []
        for part in port_input.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-')
                ports.extend(range(int(start), int(end) + 1))
            else:
                ports.append(int(part))
    else:
        ports = None
    
    logger.info(f"Banner grab: {target}")
    
    print(Colors.info(f"Grabbing banners from {target}..."))
    results = grab(target, ports)
    
    if not results:
        print(Colors.warning("No banners retrieved"))
    else:
        for port, banner in results.items():
            logger.raw(f"{target}:{port} | {banner[:100]}")

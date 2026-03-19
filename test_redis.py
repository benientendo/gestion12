#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test de connexion Redis"""
import redis

print("Connexion a Redis...")

try:
    r = redis.Redis(host="127.0.0.1", port=6379)
    result = r.ping()
    print(f"Ping : {result}")
    
    if result:
        print("\nOK - Redis fonctionne!")
        info = r.info()
        print(f"Version: {info['redis_version']}")
        print(f"Memoire utilisee: {info['used_memory_human']}")
        print(f"Connexions actives: {info['connected_clients']}")
except Exception as e:
    print(f"ERREUR: {e}")
    print("\nSolution: Verifiez que Redis tourne dans WSL avec:")
    print("  wsl redis-cli ping")

# Document d'Architecture - Proxy Chain Server

> **Architecture Decision Document**  
> Version 1.0 | 19 janvier 2026

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Principes architecturaux](#2-principes-architecturaux)
3. [Architecture système](#3-architecture-système)
4. [Architecture logicielle](#4-architecture-logicielle)
5. [Flux de données](#5-flux-de-données)
6. [Composants détaillés](#6-composants-détaillés)
7. [Modèle de données](#7-modèle-de-données)
8. [Interfaces et APIs](#8-interfaces-et-apis)
9. [Sécurité](#9-sécurité)
10. [Performance et scalabilité](#10-performance-et-scalabilité)
11. [Résilience et haute disponibilité](#11-résilience-et-haute-disponibilité)
12. [Monitoring et observabilité](#12-monitoring-et-observabilité)
13. [Déploiement](#13-déploiement)
14. [Décisions architecturales (ADR)](#14-décisions-architecturales-adr)

---

## 1. Vue d'ensemble

### 1.1 Contexte

Le Proxy Chain Server est un serveur proxy local qui permet de chaîner les requêtes HTTP/HTTPS à travers une infrastructure de proxies multi-niveaux :

```
Client → Proxy Chain Server → Proxy Corporate → Proxy Rotatif → Serveur Cible
```

### 1.2 Objectifs architecturaux

| Objectif | Description |
|----------|-------------|
| **Simplicité** | Interface unique pour le client (un seul endpoint proxy) |
| **Transparence** | Le client n'a pas besoin de connaître la chaîne de proxies |
| **Fiabilité** | Gestion automatique des défaillances |
| **Performance** | Overhead minimal sur les requêtes |
| **Extensibilité** | Ajout facile de nouvelles stratégies et fonctionnalités |

### 1.3 Contraintes

| Contrainte | Impact sur l'architecture |
|------------|---------------------------|
| Proxy corporate obligatoire | Chaînage systématique via le proxy d'entreprise |
| Protocole CONNECT pour HTTPS | Implémentation du tunneling HTTP |
| Latence réseau | Optimisation des connexions, pooling |
| Environnement Python | Utilisation des bibliothèques standards et asyncio |

---

## 2. Principes architecturaux

### 2.1 Principes fondamentaux

| Principe | Application |
|----------|-------------|
| **Single Responsibility** | Chaque composant a une responsabilité unique |
| **Dependency Injection** | Les dépendances sont injectées, pas instanciées |
| **Configuration over Code** | Le comportement est piloté par la configuration |
| **Fail Fast** | Détection rapide des erreurs, feedback immédiat |
| **Defense in Depth** | Multiples couches de validation et sécurité |

### 2.2 Patterns utilisés

| Pattern | Usage |
|---------|-------|
| **Proxy Pattern** | Interception et redirection des requêtes |
| **Chain of Responsibility** | Traitement séquentiel par les proxies |
| **Strategy Pattern** | Algorithmes de rotation interchangeables |
| **Observer Pattern** | Notification des événements (métriques, logs) |
| **Circuit Breaker** | Protection contre les proxies défaillants |
| **Object Pool** | Réutilisation des connexions |

---

## 3. Architecture système

### 3.1 Diagramme de déploiement

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Machine Locale                                  │
│                                                                             │
│  ┌─────────────────┐         ┌─────────────────────────────────────────┐   │
│  │                 │         │        Proxy Chain Server               │   │
│  │  Application    │         │  ┌─────────────────────────────────┐   │   │
│  │  Cliente        │  HTTP   │  │         HTTP Server             │   │   │
│  │  (Script Python,│────────▶│  │      (localhost:8888)           │   │   │
│  │   curl, etc.)   │         │  └───────────────┬─────────────────┘   │   │
│  │                 │         │                  │                      │   │
│  └─────────────────┘         │  ┌───────────────▼─────────────────┐   │   │
│                              │  │       Request Handler           │   │   │
│                              │  └───────────────┬─────────────────┘   │   │
│                              │                  │                      │   │
│                              │  ┌───────────────▼─────────────────┐   │   │
│                              │  │       Proxy Selector            │   │   │
│                              │  │    (Round-robin, Random, ...)   │   │   │
│                              │  └───────────────┬─────────────────┘   │   │
│                              │                  │                      │   │
│                              │  ┌───────────────▼─────────────────┐   │   │
│                              │  │      Connection Manager         │   │   │
│                              │  │   (Tunnel CONNECT, Pooling)     │   │   │
│                              │  └───────────────┬─────────────────┘   │   │
│                              └──────────────────┼──────────────────────┘   │
│                                                 │                          │
└─────────────────────────────────────────────────┼──────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Réseau Entreprise                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Proxy Corporate                                 │   │
│  │                   (proxy.entreprise.com:8080)                       │   │
│  │                                                                      │   │
│  │   • Authentification NTLM/Basic                                     │   │
│  │   • Filtrage URL                                                    │   │
│  │   • Logging centralisé                                              │   │
│  └──────────────────────────────────┬──────────────────────────────────┘   │
│                                     │                                       │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Internet                                        │
│                                                                             │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │
│  │  Proxy Rotatif │  │  Proxy Rotatif │  │  Proxy Rotatif │                │
│  │  Provider #1   │  │  Provider #1   │  │  Provider #1   │                │
│  │  (IP: x.x.x.1) │  │  (IP: x.x.x.2) │  │  (IP: x.x.x.3) │                │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                │
│          │                   │                   │                          │
│          └───────────────────┼───────────────────┘                          │
│                              │                                              │
│                              ▼                                              │
│                    ┌─────────────────┐                                      │
│                    │   API Cible     │                                      │
│                    │ api.example.com │                                      │
│                    └─────────────────┘                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Topologie réseau

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  PCS Local  │────▶│  Corp Proxy │────▶│  Rotating   │
│             │     │  :8888      │     │  :8080      │     │  Proxy Pool │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
       TCP Connection                                              │
       ═══════════════                                             ▼
       ─────────────── HTTP Request                          ┌───────────┐
                                                             │  Target   │
                                                             │   API     │
                                                             └───────────┘

Ports utilisés:
- 8888 : Proxy Chain Server (configurable)
- 8080 : Proxy Corporate (selon config entreprise)
- 7777-8080 : Proxies rotatifs (selon fournisseur)
- 443/80 : API cible
```

---

## 4. Architecture logicielle

### 4.1 Vue en couches

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COUCHE PRÉSENTATION                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │  HTTP Server  │  │  Admin API    │  │  Metrics      │               │
│  │  (Proxy)      │  │  (REST)       │  │  Endpoint     │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          COUCHE MÉTIER                                  │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │   Request     │  │    Proxy      │  │   Health      │               │
│  │   Handler     │  │   Selector    │  │   Checker     │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │   Tunnel      │  │   Retry       │  │   Circuit     │               │
│  │   Manager     │  │   Handler     │  │   Breaker     │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      COUCHE INFRASTRUCTURE                              │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │  Connection   │  │    Config     │  │    Logger     │               │
│  │  Pool         │  │    Manager    │  │               │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │   Socket      │  │   SSL/TLS     │  │   Metrics     │               │
│  │   Handler     │  │   Context     │  │   Collector   │               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Diagramme de packages

```
proxy_chain_server/
│
├── server/                    # Couche présentation
│   ├── http_server.py        # Serveur HTTP principal
│   ├── admin_api.py          # API d'administration
│   └── metrics_server.py     # Endpoint Prometheus
│
├── core/                      # Couche métier
│   ├── request_handler.py    # Traitement des requêtes
│   ├── proxy_selector.py     # Sélection des proxies
│   ├── tunnel_manager.py     # Gestion des tunnels CONNECT
│   ├── health_checker.py     # Vérification santé proxies
│   ├── retry_handler.py      # Logique de retry
│   └── circuit_breaker.py    # Protection défaillances
│
├── strategies/                # Stratégies de rotation
│   ├── base.py               # Interface abstraite
│   ├── round_robin.py        # Round-robin
│   ├── random_strategy.py    # Aléatoire
│   ├── weighted.py           # Pondéré
│   └── least_used.py         # Moins utilisé
│
├── infrastructure/            # Couche infrastructure
│   ├── connection_pool.py    # Pool de connexions
│   ├── config_manager.py     # Gestion configuration
│   ├── logger.py             # Logging structuré
│   └── metrics.py            # Collecte métriques
│
├── models/                    # Modèles de données
│   ├── proxy.py              # Modèle Proxy
│   ├── request.py            # Modèle Request
│   └── config.py             # Modèle Configuration
│
├── utils/                     # Utilitaires
│   ├── encoding.py           # Encodage Base64, etc.
│   ├── parsing.py            # Parsing URL, headers
│   └── validation.py         # Validation des données
│
├── config/                    # Configuration
│   └── default.yaml          # Configuration par défaut
│
└── main.py                    # Point d'entrée
```

### 4.3 Diagramme de classes (simplifié)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ┌─────────────────┐         ┌─────────────────┐                       │
│  │   ProxyServer   │────────▶│  RequestHandler │                       │
│  ├─────────────────┤         ├─────────────────┤                       │
│  │ - host: str     │         │ - selector      │                       │
│  │ - port: int     │         │ - tunnel_mgr    │                       │
│  │ - config        │         ├─────────────────┤                       │
│  ├─────────────────┤         │ + handle()      │                       │
│  │ + start()       │         │ + handle_connect│                       │
│  │ + stop()        │         └────────┬────────┘                       │
│  └─────────────────┘                  │                                │
│                                       │                                │
│                        ┌──────────────┴──────────────┐                 │
│                        │                             │                 │
│                        ▼                             ▼                 │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐   │
│  │      ProxySelector          │    │      TunnelManager          │   │
│  ├─────────────────────────────┤    ├─────────────────────────────┤   │
│  │ - proxies: List[Proxy]      │    │ - corp_proxy: Proxy         │   │
│  │ - strategy: RotationStrategy│    │ - connection_pool           │   │
│  │ - health_checker            │    ├─────────────────────────────┤   │
│  ├─────────────────────────────┤    │ + create_tunnel()           │   │
│  │ + get_next_proxy()          │    │ + create_chained_tunnel()   │   │
│  │ + mark_unhealthy()          │    │ + relay_data()              │   │
│  │ + get_healthy_proxies()     │    └─────────────────────────────┘   │
│  └──────────────┬──────────────┘                                       │
│                 │                                                       │
│                 ▼                                                       │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐   │
│  │   <<interface>>             │    │         Proxy               │   │
│  │   RotationStrategy          │    ├─────────────────────────────┤   │
│  ├─────────────────────────────┤    │ - host: str                 │   │
│  │ + select(proxies) -> Proxy  │    │ - port: int                 │   │
│  └──────────────┬──────────────┘    │ - username: str?            │   │
│                 │                    │ - password: str?            │   │
│    ┌────────────┼────────────┐      │ - healthy: bool             │   │
│    │            │            │      │ - stats: ProxyStats         │   │
│    ▼            ▼            ▼      ├─────────────────────────────┤   │
│ ┌──────┐   ┌──────┐   ┌──────┐     │ + get_url()                 │   │
│ │Round │   │Random│   │Weight│     │ + get_auth_header()         │   │
│ │Robin │   │      │   │ed    │     └─────────────────────────────┘   │
│ └──────┘   └──────┘   └──────┘                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Flux de données

### 5.1 Flux principal : Requête HTTPS via CONNECT

```
┌──────────┐                                                              
│  Client  │                                                              
└────┬─────┘                                                              
     │                                                                    
     │ 1. CONNECT api.example.com:443 HTTP/1.1
     │    Host: api.example.com:443
     │    Proxy-Connection: keep-alive
     │                                                                    
     ▼                                                                    
┌────────────────────────────────────────────────────────────────────────┐
│                      Proxy Chain Server                                 │
│                                                                        │
│  ┌─────────────────┐                                                   │
│  │ HTTP Server     │ 2. Parse CONNECT request                          │
│  └────────┬────────┘    Extract target: api.example.com:443            │
│           │                                                            │
│           ▼                                                            │
│  ┌─────────────────┐                                                   │
│  │ Request Handler │ 3. Get next rotating proxy                        │
│  └────────┬────────┘    Selected: proxy-fr.provider.com:7777           │
│           │                                                            │
│           ▼                                                            │
│  ┌─────────────────┐                                                   │
│  │ Tunnel Manager  │ 4. Create chained tunnel                          │
│  │                 │                                                   │
│  │  4a. Connect to corporate proxy                                     │
│  │      ─────────────────────────────────────────────▶                │
│  │      CONNECT proxy-fr.provider.com:7777 HTTP/1.1                   │
│  │      Proxy-Authorization: Basic <corp_creds>                       │
│  │      ◀─────────────────────────────────────────────                │
│  │      HTTP/1.1 200 Connection Established                           │
│  │                                                                     │
│  │  4b. Via corporate, CONNECT to rotating proxy                      │
│  │      ─────────────────────────────────────────────▶                │
│  │      CONNECT api.example.com:443 HTTP/1.1                          │
│  │      Proxy-Authorization: Basic <rotating_creds>                   │
│  │      ◀─────────────────────────────────────────────                │
│  │      HTTP/1.1 200 Connection Established                           │
│  │                                                                     │
│  └────────┬────────┘                                                   │
│           │                                                            │
│           │ 5. Return 200 to client                                    │
│           │                                                            │
└───────────┼────────────────────────────────────────────────────────────┘
            │                                                             
            ▼                                                             
┌──────────────────────────────────────────────────────────────────────┐  
│                          Tunnel Established                           │  
│                                                                       │  
│   Client ◀═══════▶ PCS ◀═══════▶ Corp ◀═══════▶ Rotating ◀═══════▶ Target
│                                                                       │  
│   6. Client sends TLS ClientHello through tunnel                      │  
│   7. TLS handshake with target server                                 │  
│   8. Encrypted HTTPS traffic flows bidirectionally                    │  
│                                                                       │  
└──────────────────────────────────────────────────────────────────────┘  
```

### 5.2 Flux de health check

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Health Checker                                   │
│                                                                         │
│   ┌─────────────┐                                                       │
│   │  Scheduler  │ ─────▶ Every 60 seconds                               │
│   └──────┬──────┘                                                       │
│          │                                                              │
│          ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │  For each proxy in pool:                                     │      │
│   │                                                              │      │
│   │  1. Create test connection via corporate proxy               │      │
│   │  2. CONNECT to rotating proxy                                │      │
│   │  3. Request test URL (e.g., https://api.ipify.org)          │      │
│   │  4. Measure response time                                    │      │
│   │  5. Validate response                                        │      │
│   │                                                              │      │
│   │  ┌─────────┐     ┌─────────┐     ┌─────────┐                │      │
│   │  │ Proxy 1 │     │ Proxy 2 │     │ Proxy 3 │                │      │
│   │  │  ✓ OK   │     │  ✗ FAIL │     │  ✓ OK   │                │      │
│   │  │  45ms   │     │ Timeout │     │  62ms   │                │      │
│   │  └─────────┘     └─────────┘     └─────────┘                │      │
│   │                                                              │      │
│   └─────────────────────────────────────────────────────────────┘      │
│          │                                                              │
│          ▼                                                              │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │  Update proxy status:                                        │      │
│   │  - Proxy 1: healthy = true, latency = 45ms                  │      │
│   │  - Proxy 2: healthy = false, consecutive_failures++         │      │
│   │  - Proxy 3: healthy = true, latency = 62ms                  │      │
│   │                                                              │      │
│   │  If consecutive_failures > 3: exclude from pool              │      │
│   │  If previously failed proxy succeeds: reintegrate            │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Flux de retry

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Retry Handler                                   │
│                                                                         │
│   Request arrives                                                       │
│        │                                                                │
│        ▼                                                                │
│   ┌─────────────────┐                                                   │
│   │  Attempt 1      │──────▶ Proxy A ──────▶ FAIL (Connection refused) │
│   │  (max_retries=3)│                                                   │
│   └────────┬────────┘                                                   │
│            │                                                            │
│            ▼                                                            │
│   ┌─────────────────┐                                                   │
│   │  Mark Proxy A   │                                                   │
│   │  as potentially │                                                   │
│   │  unhealthy      │                                                   │
│   └────────┬────────┘                                                   │
│            │                                                            │
│            ▼                                                            │
│   ┌─────────────────┐                                                   │
│   │  Attempt 2      │──────▶ Proxy B ──────▶ FAIL (Timeout)            │
│   └────────┬────────┘                                                   │
│            │                                                            │
│            ▼                                                            │
│   ┌─────────────────┐                                                   │
│   │  Attempt 3      │──────▶ Proxy C ──────▶ SUCCESS (200 OK)          │
│   └────────┬────────┘                                                   │
│            │                                                            │
│            ▼                                                            │
│   ┌─────────────────┐                                                   │
│   │  Return response│                                                   │
│   │  to client      │                                                   │
│   │                 │                                                   │
│   │  Log: 3 attempts│                                                   │
│   │  Final proxy: C │                                                   │
│   └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Composants détaillés

### 6.1 HTTP Server

**Responsabilité** : Écouter les connexions entrantes et dispatcher vers le handler approprié.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            HTTP Server                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Configuration:                                                         │
│  - bind_address: "127.0.0.1"                                           │
│  - port: 8888                                                          │
│  - max_connections: 1000                                               │
│  - timeout: 30s                                                        │
│                                                                         │
│  Comportement:                                                          │
│  - Accepte les connexions TCP                                          │
│  - Parse les requêtes HTTP                                             │
│  - Route CONNECT vers TunnelHandler                                    │
│  - Route autres méthodes vers ProxyHandler                             │
│  - Gère le keep-alive                                                  │
│                                                                         │
│  Interfaces:                                                            │
│  - IN: TCP connections                                                  │
│  - OUT: RequestHandler                                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Request Handler

**Responsabilité** : Orchestrer le traitement d'une requête.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Request Handler                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Dépendances:                                                           │
│  - ProxySelector                                                        │
│  - TunnelManager                                                        │
│  - RetryHandler                                                         │
│  - Logger                                                               │
│  - MetricsCollector                                                     │
│                                                                         │
│  Méthodes:                                                              │
│  - handle_request(request) -> response                                  │
│  - handle_connect(host, port) -> tunnel                                 │
│                                                                         │
│  Algorithme handle_connect:                                             │
│  1. Sélectionner proxy rotatif via ProxySelector                       │
│  2. Créer tunnel chaîné via TunnelManager                              │
│  3. En cas d'échec, déléguer à RetryHandler                            │
│  4. Logger la requête                                                  │
│  5. Incrémenter métriques                                              │
│  6. Retourner le tunnel au client                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Proxy Selector

**Responsabilité** : Sélectionner le prochain proxy rotatif selon la stratégie configurée.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Proxy Selector                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  État:                                                                  │
│  - proxies: List[Proxy]           # Tous les proxies configurés        │
│  - healthy_proxies: List[Proxy]   # Proxies actifs                     │
│  - strategy: RotationStrategy     # Algorithme de sélection            │
│  - current_index: int             # Pour round-robin                   │
│                                                                         │
│  Méthodes:                                                              │
│  - get_next_proxy() -> Proxy                                           │
│  - mark_unhealthy(proxy)                                               │
│  - mark_healthy(proxy)                                                 │
│  - get_all_proxies() -> List[Proxy]                                    │
│  - get_healthy_count() -> int                                          │
│                                                                         │
│  Stratégies supportées:                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ round_robin: P1 -> P2 -> P3 -> P1 -> ...                        │   │
│  │ random: Random choice among healthy proxies                      │   │
│  │ weighted: Selection based on success rate / latency             │   │
│  │ least_used: Proxy with lowest request count                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Tunnel Manager

**Responsabilité** : Créer et gérer les tunnels CONNECT chaînés.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Tunnel Manager                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Configuration:                                                         │
│  - corporate_proxy: Proxy                                              │
│  - connect_timeout: 10s                                                │
│  - read_timeout: 30s                                                   │
│                                                                         │
│  Méthodes:                                                              │
│  - create_chained_tunnel(rotating_proxy, target) -> socket             │
│  - relay_bidirectional(client_sock, server_sock)                       │
│                                                                         │
│  Algorithme create_chained_tunnel:                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ 1. TCP connect to corporate proxy                                │   │
│  │ 2. Send: CONNECT rotating_proxy:port HTTP/1.1                   │   │
│  │    + Proxy-Authorization header (if required)                   │   │
│  │ 3. Read response, expect "200 Connection Established"           │   │
│  │ 4. Through established tunnel, send:                            │   │
│  │    CONNECT target:port HTTP/1.1                                 │   │
│  │    + Proxy-Authorization header for rotating proxy              │   │
│  │ 5. Read response, expect "200 Connection Established"           │   │
│  │ 6. Return socket (now tunneled to target via chain)            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  relay_bidirectional:                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Using select() or asyncio:                                       │   │
│  │ - Read from client -> Write to server                           │   │
│  │ - Read from server -> Write to client                           │   │
│  │ - Until either side closes connection                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.5 Health Checker

**Responsabilité** : Vérifier périodiquement la disponibilité des proxies.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Health Checker                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Configuration:                                                         │
│  - check_interval: 60s                                                 │
│  - timeout: 10s                                                        │
│  - test_url: "https://api.ipify.org"                                   │
│  - failure_threshold: 3                                                │
│  - success_threshold: 2                                                │
│                                                                         │
│  État par proxy:                                                        │
│  - consecutive_failures: int                                           │
│  - consecutive_successes: int                                          │
│  - last_check: datetime                                                │
│  - last_latency: float                                                 │
│  - last_error: str?                                                    │
│                                                                         │
│  Comportement:                                                          │
│  - Thread/Task background qui vérifie chaque proxy périodiquement      │
│  - Marque unhealthy après N échecs consécutifs                         │
│  - Réintègre après M succès consécutifs                                │
│  - Continue de tester les proxies unhealthy (pour réintégration)       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Modèle de données

### 7.1 Modèle Proxy

```python
@dataclass
class Proxy:
    id: str                      # Identifiant unique
    host: str                    # Hostname ou IP
    port: int                    # Port
    protocol: str                # "http" | "https" | "socks5"
    username: Optional[str]      # Pour authentification
    password: Optional[str]      # Pour authentification
    
    # État runtime
    healthy: bool = True
    enabled: bool = True
    
    # Statistiques
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_bytes: int = 0
    avg_latency_ms: float = 0.0
    
    # Health check
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
```

### 7.2 Modèle Configuration

```python
@dataclass
class ServerConfig:
    bind_address: str = "127.0.0.1"
    port: int = 8888
    max_connections: int = 1000
    timeout_seconds: int = 30

@dataclass
class CorporateProxyConfig:
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    
@dataclass
class RotationConfig:
    strategy: str = "round_robin"  # round_robin | random | weighted | least_used
    proxies: List[ProxyConfig]

@dataclass 
class HealthCheckConfig:
    enabled: bool = True
    interval_seconds: int = 60
    timeout_seconds: int = 10
    test_url: str = "https://api.ipify.org"
    failure_threshold: int = 3
    success_threshold: int = 2

@dataclass
class RetryConfig:
    enabled: bool = True
    max_retries: int = 3
    retry_on_status: List[int] = field(default_factory=lambda: [502, 503, 504])

@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "json"
    file: Optional[str] = None

@dataclass
class MetricsConfig:
    enabled: bool = True
    port: int = 9090
    path: str = "/metrics"

@dataclass
class Config:
    server: ServerConfig
    corporate_proxy: CorporateProxyConfig
    rotation: RotationConfig
    health_check: HealthCheckConfig
    retry: RetryConfig
    logging: LoggingConfig
    metrics: MetricsConfig
```

### 7.3 Fichier de configuration YAML

```yaml
# config.yaml

server:
  bind_address: "127.0.0.1"
  port: 8888
  max_connections: 1000
  timeout_seconds: 30

corporate_proxy:
  host: "proxy.entreprise.com"
  port: 8080
  username: "${CORP_PROXY_USER}"      # Variable d'environnement
  password: "${CORP_PROXY_PASS}"

rotation:
  strategy: "round_robin"
  proxies:
    - id: "proxy-fr-1"
      host: "fr.proxy-provider.com"
      port: 7777
      protocol: "http"
      username: "user-fr"
      password: "${ROTATING_PROXY_PASS}"
      
    - id: "proxy-de-1"
      host: "de.proxy-provider.com"
      port: 7777
      protocol: "http"
      username: "user-de"
      password: "${ROTATING_PROXY_PASS}"
      
    - id: "proxy-uk-1"
      host: "uk.proxy-provider.com"
      port: 7777
      protocol: "http"
      username: "user-uk"
      password: "${ROTATING_PROXY_PASS}"

health_check:
  enabled: true
  interval_seconds: 60
  timeout_seconds: 10
  test_url: "https://api.ipify.org"
  failure_threshold: 3
  success_threshold: 2

retry:
  enabled: true
  max_retries: 3
  retry_on_status: [502, 503, 504]

logging:
  level: "INFO"
  format: "json"
  file: "/var/log/proxy-chain/server.log"

metrics:
  enabled: true
  port: 9090
  path: "/metrics"
```

---

## 8. Interfaces et APIs

### 8.1 Interface Proxy (client)

Le serveur expose une interface proxy HTTP standard :

```
Endpoint: http://127.0.0.1:8888

Méthodes supportées:
- CONNECT (pour HTTPS)
- GET, POST, PUT, DELETE, etc. (pour HTTP)

Headers reconnus:
- Proxy-Authorization: (optionnel, pour auth locale)
- X-Proxy-Sticky-Session: <session_id> (pour sticky sessions)

Exemple curl:
$ curl -x http://127.0.0.1:8888 https://api.example.com/users
```

### 8.2 API d'administration (REST)

```
Base URL: http://127.0.0.1:8889/api/v1

Endpoints:

GET /proxies
  → Liste tous les proxies configurés
  Response: {
    "proxies": [
      {
        "id": "proxy-fr-1",
        "host": "fr.proxy-provider.com",
        "port": 7777,
        "healthy": true,
        "enabled": true,
        "stats": {
          "total_requests": 1523,
          "success_rate": 0.98,
          "avg_latency_ms": 45.2
        }
      }
    ]
  }

GET /proxies/{id}
  → Détail d'un proxy

POST /proxies
  → Ajouter un proxy
  Body: { "host": "...", "port": ..., ... }

DELETE /proxies/{id}
  → Supprimer un proxy

PATCH /proxies/{id}
  → Modifier un proxy (enable/disable)
  Body: { "enabled": false }

GET /stats
  → Statistiques globales
  Response: {
    "uptime_seconds": 86400,
    "total_requests": 125000,
    "requests_per_second": 45.2,
    "active_connections": 23,
    "healthy_proxies": 8,
    "unhealthy_proxies": 2
  }

GET /health
  → Health check du serveur
  Response: { "status": "healthy" }

POST /reload
  → Recharger la configuration
```

### 8.3 Endpoint Métriques (Prometheus)

```
Endpoint: http://127.0.0.1:9090/metrics

Métriques exposées:

# Requêtes
proxy_chain_requests_total{status="success|error", proxy="proxy-fr-1"} 1523
proxy_chain_request_duration_seconds{quantile="0.5|0.9|0.99"} 0.045

# Proxies
proxy_chain_proxies_total{status="healthy|unhealthy"} 8
proxy_chain_proxy_requests_total{proxy="proxy-fr-1"} 1523
proxy_chain_proxy_errors_total{proxy="proxy-fr-1", error="timeout|refused"} 12

# Connexions
proxy_chain_active_connections 23
proxy_chain_connection_pool_size 50

# Health checks
proxy_chain_health_check_duration_seconds{proxy="proxy-fr-1"} 0.032
proxy_chain_health_check_failures_total{proxy="proxy-fr-1"} 2
```

---

## 9. Sécurité

### 9.1 Modèle de menaces

| Menace | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| Credentials exposés dans logs | Critique | Moyenne | Sanitization systématique |
| Accès non autorisé au serveur | Élevé | Faible | Bind localhost uniquement |
| Man-in-the-middle | Élevé | Faible | TLS vers proxy corporate |
| Injection de headers | Moyen | Faible | Validation stricte des inputs |
| DoS sur le serveur local | Moyen | Faible | Rate limiting, max connections |

### 9.2 Mesures de sécurité

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Sécurité en profondeur                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Couche 1 : Réseau                                                │   │
│  │ - Bind sur localhost uniquement (par défaut)                    │   │
│  │ - Aucun port exposé sur le réseau                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Couche 2 : Application                                           │   │
│  │ - Validation de tous les inputs                                 │   │
│  │ - Sanitization des logs (pas de credentials)                    │   │
│  │ - Timeout sur toutes les opérations                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Couche 3 : Configuration                                         │   │
│  │ - Credentials via variables d'environnement                     │   │
│  │ - Fichier config avec permissions restrictives (600)            │   │
│  │ - Pas de credentials en clair dans le code                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Couche 4 : Runtime                                               │   │
│  │ - Exécution en user non-privilégié                              │   │
│  │ - Pas d'accès filesystem non nécessaire                         │   │
│  │ - Conteneur avec capabilities minimales                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Gestion des credentials

```python
# Mauvais ❌
password = "secret123"
logger.info(f"Connecting with password: {password}")

# Bon ✅
password = os.environ.get("PROXY_PASSWORD")
logger.info(f"Connecting with password: ***")

# Sanitization automatique
class SecureFormatter(logging.Formatter):
    SENSITIVE_PATTERNS = [
        (r'password["\']?\s*[:=]\s*["\']?([^"\'&\s]+)', 'password=***'),
        (r'Authorization:\s*Basic\s+\S+', 'Authorization: Basic ***'),
    ]
    
    def format(self, record):
        message = super().format(record)
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            message = re.sub(pattern, replacement, message, flags=re.I)
        return message
```

---

## 10. Performance et scalabilité

### 10.1 Objectifs de performance

| Métrique | Cible | Méthode de mesure |
|----------|-------|-------------------|
| Latence P50 | < 50ms | Benchmark avec wrk |
| Latence P99 | < 100ms | Benchmark avec wrk |
| Throughput | > 1000 req/s | Benchmark avec wrk |
| Connexions simultanées | > 500 | Test de charge |
| Mémoire au repos | < 50MB | Monitoring |
| Mémoire sous charge | < 200MB | Test de charge |
| CPU au repos | < 5% | Monitoring |
| CPU sous charge | < 50% | Test de charge |

### 10.2 Optimisations

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Stratégies d'optimisation                           │
│                                                                         │
│  1. Asyncio / Event Loop                                               │
│     ─────────────────────                                              │
│     - Toutes les I/O sont non-bloquantes                              │
│     - Un seul thread gère des milliers de connexions                  │
│     - Pas de context switch coûteux                                   │
│                                                                         │
│  2. Connection Pooling                                                  │
│     ────────────────────                                               │
│     - Réutilisation des connexions vers le proxy corporate            │
│     - Pool configurable par destination                               │
│     - Keep-alive HTTP                                                  │
│                                                                         │
│  3. Buffer Management                                                   │
│     ─────────────────                                                  │
│     - Buffers de taille fixe pour éviter allocations                  │
│     - Streaming des données (pas de chargement en mémoire)            │
│     - Zero-copy quand possible                                         │
│                                                                         │
│  4. DNS Caching                                                         │
│     ───────────                                                        │
│     - Cache local des résolutions DNS                                 │
│     - TTL configurable                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.3 Scalabilité horizontale

Pour les cas nécessitant plus de capacité :

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │  (HAProxy/Nginx)│
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │   PCS #1    │   │   PCS #2    │   │   PCS #3    │
    │  :8888      │   │  :8888      │   │  :8888      │
    └─────────────┘   └─────────────┘   └─────────────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Corporate Proxy │
                    └─────────────────┘
```

---

## 11. Résilience et haute disponibilité

### 11.1 Circuit Breaker

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Circuit Breaker Pattern                          │
│                                                                         │
│   États:                                                                │
│   ┌──────────┐     failures > threshold    ┌──────────┐                │
│   │  CLOSED  │ ────────────────────────▶  │   OPEN   │                │
│   │ (normal) │                             │ (fail)   │                │
│   └────┬─────┘                             └────┬─────┘                │
│        │                                        │                      │
│        │              ┌──────────────┐          │                      │
│        │              │  HALF-OPEN   │◀─────────┘                      │
│        │              │  (testing)   │   timeout expired               │
│        │              └──────┬───────┘                                 │
│        │                     │                                         │
│        │◀────────────────────┘                                         │
│           success                                                      │
│                                                                         │
│   Configuration:                                                        │
│   - failure_threshold: 5                                               │
│   - success_threshold: 3                                               │
│   - timeout: 30s                                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Stratégies de failover

| Scénario | Action |
|----------|--------|
| Proxy rotatif indisponible | Sélection d'un autre proxy, retry |
| Tous les proxies rotatifs down | Alerte, mode dégradé ou échec |
| Proxy corporate indisponible | Échec immédiat (pas de fallback possible) |
| Timeout sur la cible | Retry avec même ou autre proxy |

### 11.3 Graceful shutdown

```python
async def shutdown(signal, loop):
    """Arrêt propre du serveur"""
    logger.info(f"Received exit signal {signal.name}")
    
    # 1. Arrêter d'accepter de nouvelles connexions
    server.close()
    
    # 2. Attendre la fin des requêtes en cours (max 30s)
    await asyncio.wait_for(
        drain_connections(),
        timeout=30.0
    )
    
    # 3. Fermer les pools de connexions
    await connection_pool.close()
    
    # 4. Sauvegarder l'état si nécessaire
    await save_state()
    
    # 5. Arrêter la boucle
    loop.stop()
```

---

## 12. Monitoring et observabilité

### 12.1 Stack de monitoring recommandée

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐          │
│   │ Proxy Chain  │────▶│  Prometheus  │────▶│   Grafana    │          │
│   │   Server     │     │              │     │              │          │
│   │  /metrics    │     └──────────────┘     └──────────────┘          │
│   └──────────────┘                                                     │
│          │                                                             │
│          │ logs (JSON)                                                 │
│          ▼                                                             │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐          │
│   │   Filebeat   │────▶│Elasticsearch │────▶│    Kibana    │          │
│   │              │     │              │     │              │          │
│   └──────────────┘     └──────────────┘     └──────────────┘          │
│                                                                         │
│   Alternatives:                                                        │
│   - Loki + Promtail pour les logs                                     │
│   - Datadog / New Relic pour tout-en-un                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Dashboards Grafana

**Dashboard principal** :
- Requêtes par seconde (global et par proxy)
- Taux de succès (global et par proxy)
- Latence (P50, P90, P99)
- Proxies healthy vs unhealthy
- Connexions actives

**Dashboard détaillé par proxy** :
- Requêtes totales
- Taux d'erreur
- Distribution des latences
- Historique health checks

### 12.3 Alertes recommandées

| Alerte | Condition | Sévérité |
|--------|-----------|----------|
| Tous proxies down | healthy_proxies == 0 | Critique |
| Majorité proxies down | healthy_proxies < 2 | Warning |
| Taux d'erreur élevé | error_rate > 10% (5min) | Warning |
| Latence élevée | P99 > 500ms (5min) | Warning |
| Mémoire élevée | memory > 80% | Warning |
| Connexions saturées | connections > 90% max | Warning |

---

## 13. Déploiement

### 13.1 Diagramme de déploiement

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Options de déploiement                           │
│                                                                         │
│  Option 1: Processus local                                             │
│  ─────────────────────────                                             │
│  $ pip install proxy-chain-server                                      │
│  $ proxy-chain-server --config config.yaml                             │
│                                                                         │
│  Option 2: Systemd service                                             │
│  ─────────────────────────                                             │
│  /etc/systemd/system/proxy-chain.service                               │
│                                                                         │
│  Option 3: Docker                                                       │
│  ────────────────────                                                  │
│  $ docker run -v ./config.yaml:/app/config.yaml \                      │
│               -p 8888:8888 \                                           │
│               proxy-chain-server:latest                                │
│                                                                         │
│  Option 4: Docker Compose                                              │
│  ────────────────────────                                              │
│  Avec Prometheus + Grafana intégrés                                    │
│                                                                         │
│  Option 5: Kubernetes                                                   │
│  ────────────────────                                                  │
│  Deployment + Service + ConfigMap + Secret                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY proxy_chain_server/ ./proxy_chain_server/
COPY config/default.yaml ./config/

# Create non-root user
RUN useradd -r -s /bin/false appuser
USER appuser

# Expose ports
EXPOSE 8888 9090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/health || exit 1

# Entry point
ENTRYPOINT ["python", "-m", "proxy_chain_server"]
CMD ["--config", "/app/config/default.yaml"]
```

### 13.3 docker-compose.yaml

```yaml
version: '3.8'

services:
  proxy-chain-server:
    build: .
    ports:
      - "8888:8888"
      - "9090:9090"
    volumes:
      - ./config.yaml:/app/config/config.yaml:ro
    environment:
      - CORP_PROXY_USER=${CORP_PROXY_USER}
      - CORP_PROXY_PASS=${CORP_PROXY_PASS}
      - ROTATING_PROXY_PASS=${ROTATING_PROXY_PASS}
    restart: unless-stopped
    networks:
      - proxy-network

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9091:9090"
    networks:
      - proxy-network

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    networks:
      - proxy-network

networks:
  proxy-network:

volumes:
  grafana-data:
```

---

## 14. Décisions architecturales (ADR)

### ADR-001: Choix de Python + Asyncio

**Statut** : Accepté

**Contexte** :  
Le serveur doit gérer de nombreuses connexions simultanées avec des opérations I/O intensives.

**Décision** :  
Utiliser Python 3.11+ avec asyncio pour la gestion asynchrone des connexions.

**Conséquences** :
- ✅ Code simple et maintenable
- ✅ Écosystème riche (aiohttp, etc.)
- ✅ Facilité de déploiement
- ❌ Performance inférieure à Go/Rust pour du pur networking
- ❌ GIL peut limiter le multi-threading

**Alternatives considérées** :
- Go : Plus performant mais moins accessible
- Node.js : Bon pour I/O mais moins typé
- Rust : Très performant mais courbe d'apprentissage

---

### ADR-002: Chaînage via double CONNECT

**Statut** : Accepté

**Contexte** :  
Le proxy corporate est obligatoire et ne peut pas être contourné.

**Décision** :  
Établir deux tunnels CONNECT successifs : vers le proxy corporate, puis vers le proxy rotatif.

**Conséquences** :
- ✅ Fonctionne avec n'importe quel proxy HTTP standard
- ✅ Transparent pour le client final
- ❌ Latence additionnelle (deux handshakes)
- ❌ Nécessite que le proxy corporate autorise CONNECT vers les ports externes

---

### ADR-003: Configuration fichier YAML + variables d'environnement

**Statut** : Accepté

**Contexte** :  
La configuration doit être flexible et sécurisée (pas de credentials en clair).

**Décision** :  
Utiliser un fichier YAML avec support des références à des variables d'environnement (`${VAR}`).

**Conséquences** :
- ✅ Configuration lisible et versionnable
- ✅ Credentials sécurisés via env vars
- ✅ Compatible avec Docker/K8s secrets
- ❌ Complexité légèrement supérieure à un simple .env

---

### ADR-004: Health check actif vs passif

**Statut** : Accepté

**Contexte** :  
Besoin de détecter les proxies défaillants sans impacter le trafic réel.

**Décision** :  
Implémenter un health check actif (requêtes périodiques de test) plutôt que passif (basé sur les erreurs du trafic réel).

**Conséquences** :
- ✅ Détection proactive des problèmes
- ✅ Proxies défaillants exclus avant impact utilisateur
- ✅ Réintégration automatique possible
- ❌ Consommation de bande passante supplémentaire
- ❌ Peut ne pas détecter tous les types de problèmes

---

*Document maintenu par l'équipe Architecture*  
*Dernière mise à jour : 19 janvier 2026*

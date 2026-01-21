# Mooltiroute - Spécifications Techniques

## 1. Architecture Globale

### 1.1 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Client                                  │
│                    (curl, requests, browser)                         │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ HTTP/HTTPS request
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MOOLTIROUTE                                  │
│                       localhost:8888                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │   main.py   │──│proxy_server │──│  tunnel.py  │                 │
│  │    (CLI)    │  │   .py       │  │  (CONNECT)  │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│         │                │                │                          │
│         ▼                ▼                ▼                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      config.py                               │   │
│  │              (YAML + env vars interpolation)                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
          [Si corporate proxy]           [Si pas corporate]
                    │                             │
                    ▼                             │
┌─────────────────────────────────┐              │
│        Corporate Proxy          │              │
│      proxy.company.com:8080     │              │
└─────────────────────────────────┘              │
                    │                             │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           WEBSHARE                                   │
│                     proxy.webshare.io:80                             │
│                   (rotation IPs côté serveur)                        │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Target Server                                │
│                       api.example.com                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Structure des Fichiers

```
mooltiroute/
├── main.py              # Point d'entrée CLI, parsing arguments
├── proxy_server.py      # Serveur HTTP proxy asyncio
├── tunnel.py            # Gestion tunnels CONNECT (simple et chaîné)
├── config.py            # Chargement YAML, interpolation env vars
├── config.yaml          # Configuration par défaut
├── requirements.txt     # Dépendances (pyyaml>=6.0)
├── README.md            # Documentation utilisateur
├── CLAUDE.md            # Instructions pour Claude Code
└── docs/
    ├── PRD.md           # Product Requirements Document
    └── TECHNICAL_SPECS.md  # Ce document
```

---

## 2. Spécifications des Modules

### 2.1 Module `config.py`

#### 2.1.1 Responsabilités

- Charger et parser fichier YAML
- Interpoler variables d'environnement (`${VAR_NAME}`)
- Valider la configuration
- Exposer dataclasses typées

#### 2.1.2 Dataclasses

```python
@dataclass
class ServerConfig:
    """Configuration du serveur local."""
    host: str = "127.0.0.1"  # Adresse d'écoute
    port: int = 8888          # Port d'écoute

@dataclass
class ProxyConfig:
    """Configuration d'un proxy (webshare ou corporate)."""
    host: str                 # Hostname du proxy
    port: int                 # Port du proxy
    username: str = ""        # Username (optionnel)
    password: str = ""        # Password (optionnel)

    @property
    def requires_auth(self) -> bool:
        """True si authentification requise."""

    @property
    def auth_header(self) -> str | None:
        """Header Proxy-Authorization encodé base64."""

    @property
    def address(self) -> tuple[str, int]:
        """Tuple (host, port)."""

@dataclass
class LoggingConfig:
    """Configuration du logging."""
    level: str = "INFO"       # DEBUG, INFO, WARNING, ERROR

@dataclass
class Config:
    """Configuration principale."""
    server: ServerConfig
    webshare: ProxyConfig
    corporate_proxy: ProxyConfig | None = None
    logging: LoggingConfig
```

#### 2.1.3 Fonctions

```python
def load_config(path: str) -> Config:
    """
    Charge config depuis fichier YAML avec interpolation env vars.

    Args:
        path: Chemin vers le fichier YAML

    Returns:
        Config: Configuration parsée et validée

    Raises:
        ConfigError: Si fichier manquant, YAML invalide, ou config incomplète
    """

def interpolate_env_vars(value: str) -> str:
    """
    Remplace ${VAR} par os.environ.get('VAR', '').

    Args:
        value: Chaîne contenant potentiellement des ${VAR}

    Returns:
        str: Chaîne avec variables interpolées
    """
```

#### 2.1.4 Interpolation des Variables d'Environnement

| Pattern | Résultat |
|---------|----------|
| `${VAR}` | Valeur de `os.environ['VAR']` |
| `${VAR}` (non définie) | Chaîne vide `""` |
| `texte${VAR}suite` | Concaténation avec la valeur |

---

### 2.2 Module `tunnel.py`

#### 2.2.1 Responsabilités

- Établir tunnel CONNECT vers un proxy
- Créer tunnel chaîné (corporate → webshare)
- Relayer données bidirectionnellement

#### 2.2.2 Constantes

```python
CONNECT_TIMEOUT = 30   # Timeout connexion en secondes
BUFFER_SIZE = 65536    # Taille buffer pour relay (64 KB)
```

#### 2.2.3 Exceptions

```python
class TunnelError(Exception):
    """Erreur d'établissement de tunnel."""
    message: str       # Message d'erreur
    status_code: int   # Code HTTP (défaut: 502)
```

#### 2.2.4 Fonctions

```python
async def create_tunnel(
    target_host: str,
    target_port: int,
    proxy: ProxyConfig,
    existing_connection: tuple[StreamReader, StreamWriter] | None = None
) -> tuple[StreamReader, StreamWriter]:
    """
    Établit un tunnel CONNECT vers target via proxy.

    Args:
        target_host: Hostname de la destination
        target_port: Port de la destination
        proxy: Configuration du proxy à utiliser
        existing_connection: Connexion existante (pour chaînage)

    Returns:
        tuple: (reader, writer) du tunnel établi

    Raises:
        TunnelError: Si le proxy refuse la connexion (non-2xx)
    """

async def create_chained_tunnel(
    target_host: str,
    target_port: int,
    corporate: ProxyConfig,
    webshare: ProxyConfig
) -> tuple[StreamReader, StreamWriter]:
    """
    Crée double tunnel : corporate → webshare → target.

    Étapes:
    1. Connecte à corporate proxy (TCP)
    2. CONNECT vers webshare via corporate
    3. CONNECT vers target via webshare

    Args:
        target_host: Hostname de la destination finale
        target_port: Port de la destination finale
        corporate: Configuration du proxy corporate
        webshare: Configuration du proxy Webshare

    Returns:
        tuple: (reader, writer) du tunnel établi

    Raises:
        TunnelError: Si un des proxies refuse la connexion
    """

async def relay_data(
    client_reader: StreamReader,
    client_writer: StreamWriter,
    remote_reader: StreamReader,
    remote_writer: StreamWriter
) -> None:
    """
    Relaye données bidirectionnellement jusqu'à fermeture.

    Utilise asyncio.gather pour les deux directions simultanément.
    Se termine quand une des connexions se ferme.
    """
```

#### 2.2.5 Format Requête CONNECT

```http
CONNECT target.com:443 HTTP/1.1
Host: target.com:443
Proxy-Authorization: Basic <base64(user:pass)>

```

**Notes:**
- Ligne vide finale obligatoire
- `Proxy-Authorization` uniquement si proxy requiert auth
- Réponse attendue: `HTTP/1.1 200 Connection Established`

---

### 2.3 Module `proxy_server.py`

#### 2.3.1 Responsabilités

- Écouter sur host:port configuré
- Parser requêtes HTTP entrantes
- Router CONNECT vers tunnel HTTPS
- Router autres méthodes vers forward HTTP

#### 2.3.2 Classe ProxyServer

```python
class ProxyServer:
    """Serveur proxy HTTP/HTTPS."""

    def __init__(self, config: Config, use_corporate: bool = True):
        """
        Initialise le serveur proxy.

        Args:
            config: Configuration chargée
            use_corporate: Utiliser le proxy corporate si configuré
        """

    async def start(self) -> None:
        """Démarre le serveur asyncio. Bloque jusqu'à arrêt."""

    async def stop(self) -> None:
        """Arrête proprement le serveur."""

    async def handle_client(
        self,
        reader: StreamReader,
        writer: StreamWriter
    ) -> None:
        """
        Gère une connexion client entrante.

        Dispatch vers handle_connect ou handle_http selon la méthode.
        """

    async def handle_connect(
        self,
        target: str,
        client_reader: StreamReader,
        client_writer: StreamWriter
    ) -> None:
        """
        Gère requête CONNECT (HTTPS tunneling).

        1. Parse host:port depuis target
        2. Établit tunnel (simple ou chaîné)
        3. Répond 200 Connection Established
        4. Relaye données bidirectionnellement
        """

    async def handle_http(
        self,
        method: str,
        url: str,
        headers: dict,
        body: bytes,
        client_writer: StreamWriter
    ) -> None:
        """
        Gère requête HTTP standard (GET, POST, etc.).

        1. Parse URL pour extraire host/port/path
        2. Connecte au proxy (corporate ou webshare)
        3. Forward la requête avec auth proxy
        4. Relaye la réponse au client
        """
```

#### 2.3.3 Parsing des Requêtes

| Requête entrante | Handler | Action |
|-----------------|---------|--------|
| `CONNECT api.example.com:443 HTTP/1.1` | `handle_connect` | Tunnel HTTPS |
| `GET http://example.com/path HTTP/1.1` | `handle_http` | Forward HTTP |
| `POST http://example.com/api HTTP/1.1` | `handle_http` | Forward HTTP |

#### 2.3.4 Réponses au Client

| Code | Message | Situation |
|------|---------|-----------|
| 200 | Connection Established | Tunnel HTTPS établi |
| 400 | Bad Request | Requête malformée |
| 502 | Bad Gateway | Erreur connexion proxy |

---

### 2.4 Module `main.py`

#### 2.4.1 Arguments CLI

| Argument | Type | Défaut | Description |
|----------|------|--------|-------------|
| `--config`, `-c` | str | `config.yaml` | Chemin fichier config |
| `--no-corporate` | flag | false | Désactive proxy corporate |
| `--verbose`, `-v` | flag | false | Logs détaillés (DEBUG) |

#### 2.4.2 Comportement

1. Parser arguments CLI
2. Charger configuration YAML
3. Configurer logging selon niveau
4. Afficher résumé configuration
5. Installer handlers SIGINT/SIGTERM
6. Démarrer serveur proxy
7. Attendre signal d'arrêt
8. Arrêt propre du serveur

---

## 3. Flux de Données

### 3.1 Requête HTTPS sans Corporate Proxy

```
Client                    Mooltiroute                 Webshare                Target
  │                           │                          │                      │
  │ CONNECT api.com:443       │                          │                      │
  │──────────────────────────>│                          │                      │
  │                           │ TCP connect              │                      │
  │                           │─────────────────────────>│                      │
  │                           │ CONNECT api.com:443      │                      │
  │                           │ Proxy-Auth: Basic xxx    │                      │
  │                           │─────────────────────────>│                      │
  │                           │ 200 Connection Established                      │
  │                           │<─────────────────────────│                      │
  │ 200 Connection Established│                          │                      │
  │<──────────────────────────│                          │                      │
  │                           │                          │                      │
  │ TLS ClientHello           │ relay                    │ relay                │
  │──────────────────────────>│─────────────────────────>│─────────────────────>│
  │                           │                          │                      │
  │ TLS ServerHello           │ relay                    │ relay                │
  │<──────────────────────────│<─────────────────────────│<─────────────────────│
  │                           │                          │                      │
  │ HTTPS data                │ relay                    │ relay                │
  │<─────────────────────────>│<────────────────────────>│<────────────────────>│
```

### 3.2 Requête HTTPS avec Corporate Proxy (Double Tunneling)

```
Client              Mooltiroute           Corporate            Webshare           Target
  │                     │                     │                    │                 │
  │ CONNECT api.com:443 │                     │                    │                 │
  │────────────────────>│                     │                    │                 │
  │                     │ TCP connect         │                    │                 │
  │                     │────────────────────>│                    │                 │
  │                     │ CONNECT webshare:80 │                    │                 │
  │                     │ Proxy-Auth: corp    │                    │                 │
  │                     │────────────────────>│                    │                 │
  │                     │ 200 Established     │                    │                 │
  │                     │<────────────────────│                    │                 │
  │                     │                     │                    │                 │
  │                     │ CONNECT api.com:443 (via tunnel corp)    │                 │
  │                     │ Proxy-Auth: webshare│                    │                 │
  │                     │─────────────────────│───────────────────>│                 │
  │                     │ 200 Established     │                    │                 │
  │                     │<────────────────────│────────────────────│                 │
  │                     │                     │                    │                 │
  │ 200 Established     │                     │                    │                 │
  │<────────────────────│                     │                    │                 │
  │                     │                     │                    │                 │
  │ TLS + HTTPS data    │            relay through both tunnels    │                 │
  │<───────────────────>│<───────────────────>│<──────────────────>│<───────────────>│
```

### 3.3 Requête HTTP (GET/POST)

```
Client              Mooltiroute                    Webshare               Target
  │                     │                              │                     │
  │ GET http://x.com/   │                              │                     │
  │────────────────────>│                              │                     │
  │                     │ TCP connect                  │                     │
  │                     │─────────────────────────────>│                     │
  │                     │ GET http://x.com/ HTTP/1.1   │                     │
  │                     │ Proxy-Auth: Basic xxx        │                     │
  │                     │─────────────────────────────>│                     │
  │                     │                              │ GET / HTTP/1.1      │
  │                     │                              │────────────────────>│
  │                     │                              │ HTTP/1.1 200 OK     │
  │                     │                              │<────────────────────│
  │                     │ HTTP/1.1 200 OK              │                     │
  │                     │<─────────────────────────────│                     │
  │ HTTP/1.1 200 OK     │                              │                     │
  │<────────────────────│                              │                     │
```

---

## 4. Configuration

### 4.1 Format YAML

```yaml
# config.yaml - Configuration Mooltiroute

server:
  host: "127.0.0.1"    # Bind uniquement localhost pour sécurité
  port: 8888           # Port d'écoute

webshare:
  host: "proxy.webshare.io"
  port: 80
  username: "${WEBSHARE_USER}"   # Via variable d'environnement
  password: "${WEBSHARE_PASS}"   # Via variable d'environnement

# Section optionnelle - commenter si pas de corporate proxy
corporate_proxy:
  host: "proxy.company.com"
  port: 8080
  username: "${CORP_PROXY_USER}"
  password: "${CORP_PROXY_PASS}"

logging:
  level: "INFO"        # DEBUG, INFO, WARNING, ERROR
```

### 4.2 Variables d'Environnement

| Variable | Description | Obligatoire |
|----------|-------------|-------------|
| `WEBSHARE_USER` | Username Webshare | Oui |
| `WEBSHARE_PASS` | Password Webshare | Oui |
| `CORP_PROXY_USER` | Username proxy corporate | Si corporate |
| `CORP_PROXY_PASS` | Password proxy corporate | Si corporate |

### 4.3 Priorité de Configuration

1. Variables d'environnement (via `${VAR}` dans YAML)
2. Valeurs directes dans config.yaml
3. Valeurs par défaut des dataclasses

---

## 5. Logging

### 5.1 Format

```
2024-01-15 10:23:45 INFO  [mooltiroute.proxy_server] Started on 127.0.0.1:8888
2024-01-15 10:23:46 INFO  [mooltiroute.proxy_server] CONNECT api.example.com:443
2024-01-15 10:23:46 INFO  [mooltiroute.proxy_server] CONNECT api.example.com:443 -> 200
2024-01-15 10:23:47 DEBUG [mooltiroute.tunnel] Starting bidirectional relay
2024-01-15 10:23:48 ERROR [mooltiroute.tunnel] Connection refused to webshare
```

### 5.2 Niveaux

| Niveau | Contenu |
|--------|---------|
| DEBUG | Détails relay, requêtes CONNECT envoyées, réponses complètes |
| INFO | Requêtes reçues, connexions établies, démarrage/arrêt |
| WARNING | Timeouts, connexions interrompues |
| ERROR | Échecs connexion, erreurs auth, exceptions |

### 5.3 Sécurité

**Les credentials ne sont JAMAIS loggés**, même en niveau DEBUG.

Exemple de sanitization :
```python
# BON
logger.info(f"Webshare auth: {config.webshare.username}:****")

# MAUVAIS (NE JAMAIS FAIRE)
logger.debug(f"Auth header: {proxy.auth_header}")
```

---

## 6. Gestion des Erreurs

### 6.1 Erreurs de Configuration

| Erreur | Cause | Comportement |
|--------|-------|--------------|
| `ConfigError: Configuration file not found` | Fichier YAML manquant | Exit code 1 |
| `ConfigError: Invalid YAML` | Syntaxe YAML incorrecte | Exit code 1 |
| `ConfigError: Missing required 'webshare'` | Section webshare absente | Exit code 1 |

### 6.2 Erreurs Runtime

| Erreur | Cause | Réponse Client |
|--------|-------|----------------|
| `TunnelError: Connection timeout` | Proxy injoignable | 502 Bad Gateway |
| `TunnelError: Proxy returned 407` | Auth échouée | 502 Bad Gateway |
| `TunnelError: Connection refused` | Port fermé | 502 Bad Gateway |
| Requête malformée | HTTP invalide | 400 Bad Request |

### 6.3 Codes de Sortie

| Code | Signification |
|------|---------------|
| 0 | Arrêt normal (SIGINT/SIGTERM) |
| 1 | Erreur de configuration |
| 2 | Erreur au démarrage du serveur |

---

## 7. Sécurité

### 7.1 Mesures Implémentées

| Mesure | Description |
|--------|-------------|
| Bind localhost | Par défaut `127.0.0.1`, pas d'accès réseau externe |
| Credentials via env vars | Pas de mots de passe en dur dans le code |
| Pas de log credentials | Sanitization systématique |
| Timeout connexions | 30 secondes max pour éviter les blocages |

### 7.2 Recommandations Déploiement

1. **Ne jamais exposer sur 0.0.0.0** en production
2. **Utiliser des variables d'environnement** pour les credentials
3. **Restreindre les permissions** du fichier config.yaml (`chmod 600`)
4. **Logs en mode INFO** en production (pas DEBUG)

---

## 8. Performance

### 8.1 Caractéristiques

| Aspect | Implémentation |
|--------|----------------|
| Concurrence | asyncio (single thread, non-blocking I/O) |
| Buffer | 64 KB pour relay bidirectionnel |
| Connexions | Illimitées (limité par OS/ulimit) |
| Mémoire | ~10 MB au repos, ~100 KB par connexion active |

### 8.2 Benchmarks Attendus

| Métrique | Valeur cible |
|----------|--------------|
| Latence ajoutée | < 10ms (sans proxy corporate) |
| Latence ajoutée | < 20ms (avec proxy corporate) |
| Throughput | > 100 MB/s en relay |
| Connexions simultanées | > 1000 |

---

## 9. Tests de Vérification

### 9.1 Installation

```bash
# Cloner le repo
git clone <repo-url>
cd mooltiroute

# Installer dépendances
pip install -r requirements.txt

# Configurer credentials
export WEBSHARE_USER="your_username"
export WEBSHARE_PASS="your_password"
```

### 9.2 Tests Manuels

```bash
# 1. Démarrer le serveur
python main.py -v

# 2. Test HTTP (autre terminal)
curl -x http://127.0.0.1:8888 http://httpbin.org/ip
# Attendu: {"origin": "<IP Webshare>"}

# 3. Test HTTPS
curl -x http://127.0.0.1:8888 https://api.ipify.org
# Attendu: <IP Webshare>

# 4. Vérifier rotation IP
for i in {1..5}; do
  curl -s -x http://127.0.0.1:8888 https://api.ipify.org
  echo
  sleep 1
done
# Attendu: IPs différentes à chaque requête

# 5. Test mode --no-corporate
python main.py --no-corporate -v
# Logs: "Corporate proxy: disabled"
```

### 9.3 Tests avec Different Clients

```python
# Python requests
import requests
proxies = {"http": "http://127.0.0.1:8888", "https": "http://127.0.0.1:8888"}
response = requests.get("https://api.ipify.org", proxies=proxies)
print(response.text)
```

```javascript
// Node.js axios
const axios = require('axios');
const HttpsProxyAgent = require('https-proxy-agent');

const agent = new HttpsProxyAgent('http://127.0.0.1:8888');
axios.get('https://api.ipify.org', { httpsAgent: agent })
  .then(res => console.log(res.data));
```

---

## 10. Évolutions Futures (v2+)

| Feature | Description | Priorité |
|---------|-------------|----------|
| Métriques Prometheus | Compteurs requêtes, latences, erreurs | Haute |
| Health checks | Vérification périodique Webshare | Haute |
| API REST admin | Endpoints /status, /config | Moyenne |
| Retry avec backoff | Réessai automatique sur erreur temporaire | Moyenne |
| Multi-provider | Support autres providers (Bright Data, etc.) | Basse |
| Sticky sessions | Même IP pour une session client | Basse |

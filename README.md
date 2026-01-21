# Mooltiroute

**Serveur proxy local pour router vos requêtes HTTP/HTTPS via un proxy rotatif (Webshare).**

Mooltiroute agit comme point d'entrée unique (`localhost:8888`) qui gère automatiquement l'authentification et le routage vers Webshare, avec support optionnel d'un proxy corporate intermédiaire.

```
┌────────┐      ┌─────────────┐      ┌──────────┐      ┌────────┐
│ Client │ ───▶ │ Mooltiroute │ ───▶ │ Webshare │ ───▶ │ Target │
│        │      │ :8888       │      │ (rotate) │      │        │
└────────┘      └─────────────┘      └──────────┘      └────────┘
```

## Pourquoi Mooltiroute ?

| Problème | Solution Mooltiroute |
|----------|---------------------|
| Configuration proxy différente pour chaque outil | Endpoint unique `localhost:8888` |
| Credentials à gérer partout | Configuration centralisée |
| Double proxy (corporate + rotatif) complexe | Tunneling automatique |
| Rate-limiting par IP | Rotation IP transparente |

### Avant / Après

```bash
# AVANT - Configuration complexe
curl -x http://user:pass@proxy.webshare.io:80 https://api.com
export HTTPS_PROXY="http://user:pass@proxy.webshare.io:80"
requests.get(url, proxies={"https": "http://user:pass@..."})

# APRÈS - Simple et uniforme
curl -x http://localhost:8888 https://api.com
export HTTPS_PROXY="http://localhost:8888"
requests.get(url, proxies={"https": "http://localhost:8888"})
```

## Installation

### Prérequis

- Python 3.10+
- Compte [Webshare](https://www.webshare.io/) avec credentials proxy
- **OS supportés** : Linux, macOS, Windows (natif ou WSL)

### Installation

```bash
# Cloner le repository
git clone https://github.com/your-username/mooltiroute.git
cd mooltiroute

# Installer les dépendances
pip install -r requirements.txt
```

## Configuration

### 1. Obtenir les credentials d'un proxy rotatif

> **Note** : Nous utilisons [Webshare](https://www.webshare.io/) à titre d'exemple car il propose une offre gratuite (10 proxies) permettant de tester Mooltiroute sans engagement. Tout autre fournisseur de proxy rotatif HTTP fonctionne également.

#### Étape 1 : Créer un compte gratuit

Rendez-vous sur [webshare.io](https://www.webshare.io/) et cliquez sur **"Get 10 Proxies for free"** pour créer un compte gratuit.

![Webshare - Page d'accueil](docs/images/webshare-01-homepage.png)

#### Étape 2 : Récupérer les credentials du proxy rotatif

Une fois connecté, dans le menu de gauche :
1. Accédez à **Free > Proxy List**
2. Dans **Connection Method**, sélectionnez **"Rotating Proxy Endpoint"**
3. Copiez les 4 informations affichées (boutons **COPY**) :

![Webshare - Credentials proxy rotatif](docs/images/webshare-03-credentials.png)

| Champ | Valeur typique |
|-------|----------------|
| **Domain Name** | `p.webshare.io` |
| **Proxy Port** | `80` |
| **Proxy Username** | votre username |
| **Proxy Password** | votre password |

### 2. Variables d'environnement (recommandé)

**Linux/macOS (bash/zsh) :**
```bash
# Credentials Webshare (obligatoire)
export WEBSHARE_USER="votre_username"
export WEBSHARE_PASS="votre_password"

# Credentials proxy corporate (optionnel)
export CORP_PROXY_USER="votre_username_corp"
export CORP_PROXY_PASS="votre_password_corp"
```

**Windows CMD :**
```cmd
set WEBSHARE_USER=votre_username
set WEBSHARE_PASS=votre_password

:: Optionnel - proxy corporate
set CORP_PROXY_USER=votre_username_corp
set CORP_PROXY_PASS=votre_password_corp
```

**Windows PowerShell :**
```powershell
$env:WEBSHARE_USER = "votre_username"
$env:WEBSHARE_PASS = "votre_password"

# Optionnel - proxy corporate
$env:CORP_PROXY_USER = "votre_username_corp"
$env:CORP_PROXY_PASS = "votre_password_corp"
```

### 3. Fichier config.yaml

```yaml
# config.yaml
server:
  host: "127.0.0.1"
  port: 8888

webshare:
  host: "proxy.webshare.io"
  port: 80
  username: "${WEBSHARE_USER}"
  password: "${WEBSHARE_PASS}"

# Optionnel - décommenter si proxy corporate
# corporate_proxy:
#   host: "proxy.company.com"
#   port: 8080
#   username: "${CORP_PROXY_USER}"
#   password: "${CORP_PROXY_PASS}"

logging:
  level: "INFO"
```

> **Note** : Les patterns `${VAR}` sont automatiquement remplacés par les variables d'environnement correspondantes.

## Utilisation

### Démarrage

```bash
# Mode par défaut
python main.py

# Avec logs détaillés
python main.py --verbose

# Sans proxy corporate (même si configuré)
python main.py --no-corporate

# Avec fichier de config personnalisé
python main.py --config /path/to/config.yaml
```

### Options CLI

| Option | Description |
|--------|-------------|
| `-c`, `--config` | Chemin vers le fichier de configuration (défaut: `config.yaml`) |
| `--no-corporate` | Désactive le proxy corporate, connexion directe à Webshare |
| `-v`, `--verbose` | Active les logs détaillés (niveau DEBUG) |

### Exemple de sortie

```
2024-01-15 10:23:45 INFO  [mooltiroute] ==================================================
2024-01-15 10:23:45 INFO  [mooltiroute] Mooltiroute - Proxy Chain Server
2024-01-15 10:23:45 INFO  [mooltiroute] ==================================================
2024-01-15 10:23:45 INFO  [mooltiroute] Listen: 127.0.0.1:8888
2024-01-15 10:23:45 INFO  [mooltiroute] Webshare: proxy.webshare.io:80
2024-01-15 10:23:45 INFO  [mooltiroute] Webshare auth: myuser:****
2024-01-15 10:23:45 INFO  [mooltiroute] Corporate proxy: disabled
2024-01-15 10:23:45 INFO  [mooltiroute] ==================================================
2024-01-15 10:23:45 INFO  [mooltiroute.proxy_server] Started on 127.0.0.1:8888 (direct to webshare)
```

## Tests

### Test rapide

```bash
# Terminal 1 - Démarrer Mooltiroute
python main.py -v

# Terminal 2 - Tester
curl -x http://127.0.0.1:8888 https://api.ipify.org
```

### Vérifier la rotation d'IP

```bash
# Devrait afficher des IPs différentes
for i in {1..5}; do
  curl -s -x http://127.0.0.1:8888 https://api.ipify.org
  echo
  sleep 1
done
```

### Avec Python requests

```python
import requests

proxies = {
    "http": "http://127.0.0.1:8888",
    "https": "http://127.0.0.1:8888"
}

response = requests.get("https://api.ipify.org", proxies=proxies)
print(f"IP: {response.text}")
```

### Avec Node.js

```javascript
const axios = require('axios');
const HttpsProxyAgent = require('https-proxy-agent');

const agent = new HttpsProxyAgent('http://127.0.0.1:8888');
axios.get('https://api.ipify.org', { httpsAgent: agent })
  .then(res => console.log(`IP: ${res.data}`));
```

### Configuration système (optionnel)

```bash
# Configurer le proxy pour tout le système
export HTTP_PROXY="http://127.0.0.1:8888"
export HTTPS_PROXY="http://127.0.0.1:8888"

# Puis toutes les commandes utilisent automatiquement le proxy
curl https://api.ipify.org
wget https://api.ipify.org -qO-
```

## Architecture

```
mooltiroute/
├── main.py              # CLI et point d'entrée
├── proxy_server.py      # Serveur proxy asyncio
├── tunnel.py            # Gestion tunnels CONNECT
├── config.py            # Chargement configuration
├── config.yaml          # Configuration par défaut
├── requirements.txt     # Dépendances
└── docs/
    ├── PRD.md           # Product Requirements Document
    └── TECHNICAL_SPECS.md  # Spécifications techniques
```

### Flux de données

**Sans proxy corporate :**
```
Client → Mooltiroute → Webshare → Target
```

**Avec proxy corporate (double tunneling) :**
```
Client → Mooltiroute → Corporate Proxy → Webshare → Target
```

## Fonctionnalités

### Supporté (v1.0)

- [x] Proxy HTTP et HTTPS (méthode CONNECT)
- [x] Authentification Webshare
- [x] Double tunneling (corporate → webshare)
- [x] Configuration YAML avec interpolation env vars
- [x] Option `--no-corporate` pour bypass
- [x] Logging configurable (DEBUG/INFO/WARNING/ERROR)
- [x] Arrêt propre (Ctrl+C sur tous les OS, SIGTERM sur Unix/macOS)
- [x] Bind localhost uniquement (sécurité)

### Non supporté (v1.0)

- [ ] Métriques Prometheus
- [ ] API REST d'administration
- [ ] Health checks automatiques
- [ ] Retry avec backoff
- [ ] Support SOCKS5
- [ ] Multi-provider (autres que Webshare)

## Résolution de problèmes

### Erreur "Connection refused"

```
TunnelError: Connection refused to proxy.webshare.io:80
```

**Solutions :**
1. Vérifier que les credentials Webshare sont corrects
2. Vérifier que votre IP est autorisée sur Webshare
3. Tester la connexion directe : `curl -x http://user:pass@proxy.webshare.io:80 http://httpbin.org/ip`

### Erreur "407 Proxy Authentication Required"

```
TunnelError: Proxy returned 407 Proxy Authentication Required
```

**Solutions :**
1. Vérifier les variables d'environnement : `echo $WEBSHARE_USER`
2. Vérifier le config.yaml pour les patterns `${VAR}`
3. Tester les credentials directement sur Webshare

### Erreur "Configuration file not found"

```
ConfigError: Configuration file not found: config.yaml
```

**Solutions :**
1. Créer le fichier config.yaml à la racine du projet
2. Spécifier le chemin complet : `python main.py -c /chemin/vers/config.yaml`

### Timeout sur proxy corporate

```
TunnelError: Connection timeout to corporate proxy
```

**Solutions :**
1. Vérifier que le proxy corporate est accessible
2. Tester : `curl -x http://proxy.company.com:8080 http://httpbin.org/ip`
3. Utiliser `--no-corporate` pour bypasser

## Sécurité

- **Bind localhost uniquement** : Par défaut, Mooltiroute n'écoute que sur `127.0.0.1`
- **Credentials via env vars** : Jamais de mots de passe en dur
- **Logs sanitisés** : Les mots de passe ne sont jamais loggés
- **Permissions fichier** : Protégez config.yaml
  - Linux/macOS : `chmod 600 config.yaml`
  - Windows : Clic droit → Propriétés → Sécurité → Restreindre l'accès à votre utilisateur

## Documentation

- [PRD - Product Requirements Document](docs/PRD.md)
- [Spécifications Techniques](docs/TECHNICAL_SPECS.md)

## Licence

MIT

## Contribution

Les contributions sont bienvenues. Merci d'ouvrir une issue avant de soumettre une PR pour discuter des changements proposés.

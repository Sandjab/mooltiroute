# Mooltiroute - Product Requirements Document (PRD)

## 1. Executive Summary

**Mooltiroute** est un serveur proxy local qui agit comme point d'entrée unique pour router les requêtes HTTP/HTTPS vers un service de proxy rotatif (Webshare), avec support optionnel d'un proxy corporate intermédiaire.

| Attribut | Valeur |
|----------|--------|
| **Version** | 1.0.0 |
| **Statut** | En développement |
| **Langage** | Python 3.10+ |
| **Licence** | MIT |

---

## 2. Contexte et Problématique

### 2.1 Contexte

Lors d'appels API fréquents vers des services tiers, les clients peuvent être :
- **Rate-limités** : Nombre de requêtes par minute/heure dépassé
- **Bloqués par IP** : Détection de comportement automatisé
- **Géo-restreints** : Accès limité à certaines régions

Les proxies rotatifs (comme Webshare) permettent de distribuer les requêtes sur différentes IPs, contournant ces limitations.

### 2.2 Problèmes Identifiés

| # | Problème | Impact |
|---|----------|--------|
| 1 | **Complexité de configuration** | Chaque outil (curl, Python requests, Node.js axios) a sa propre syntaxe pour configurer un proxy authentifié |
| 2 | **Proxy corporate obligatoire** | En environnement entreprise, les requêtes doivent d'abord traverser un proxy corporate avant d'atteindre Internet |
| 3 | **Double tunneling complexe** | Configurer un proxy qui passe par un autre proxy est techniquement difficile |
| 4 | **Gestion des credentials** | Les credentials proxy doivent être gérés de manière sécurisée et centralisée |
| 5 | **Pas de solution unifiée** | Absence d'outil simple pour centraliser la configuration proxy |

### 2.3 Solution Proposée

**Mooltiroute** résout ces problèmes en offrant :

```
┌─────────────────────────────────────────────────────────────────┐
│  AVANT : Configuration complexe par outil                       │
├─────────────────────────────────────────────────────────────────┤
│  curl -x http://user:pass@proxy.webshare.io:80 https://api.com  │
│  requests.get(url, proxies={"https": "http://user:pass@..."})   │
│  axios.get(url, { proxy: { host: "...", auth: {...} } })        │
└─────────────────────────────────────────────────────────────────┘

                              ▼

┌─────────────────────────────────────────────────────────────────┐
│  APRÈS : Configuration unique et simple                         │
├─────────────────────────────────────────────────────────────────┤
│  curl -x http://localhost:8888 https://api.com                  │
│  requests.get(url, proxies={"https": "http://localhost:8888"})  │
│  axios.get(url, { proxy: { host: "localhost", port: 8888 } })   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Utilisateurs Cibles

### 3.1 Personas

#### Persona 1 : Développeur Backend
- **Profil** : Développeur effectuant des appels API vers des services tiers
- **Besoin** : Éviter le rate-limiting lors de tests ou scraping
- **Environnement** : macOS/Linux, terminal, scripts Python/Node.js
- **Point de douleur** : Configuration proxy différente pour chaque outil

#### Persona 2 : Data Engineer
- **Profil** : Ingénieur data collectant des données depuis des APIs
- **Besoin** : Rotation d'IP automatique pour éviter les blocages
- **Environnement** : Serveurs Linux, pipelines automatisés
- **Point de douleur** : Gestion des credentials dans les pipelines CI/CD

#### Persona 3 : DevOps en Entreprise
- **Profil** : DevOps travaillant derrière un proxy corporate
- **Besoin** : Accéder à des services externes via proxy rotatif + proxy corporate
- **Environnement** : Réseau d'entreprise avec proxy obligatoire
- **Point de douleur** : Double tunneling impossible à configurer simplement

### 3.2 Cas d'Usage

| ID | Cas d'Usage | Priorité | Persona |
|----|-------------|----------|---------|
| UC1 | Appels API avec rotation d'IP | Must | 1, 2 |
| UC2 | Scraping web avec anonymisation | Must | 2 |
| UC3 | Accès Internet via proxy corporate + rotatif | Must | 3 |
| UC4 | Tests d'intégration avec IPs variées | Should | 1 |
| UC5 | Contournement géo-restrictions (légal) | Could | 1, 2 |

---

## 4. Exigences Fonctionnelles

### 4.1 Core Features (Must Have)

| ID | Exigence | Description | Critère d'acceptation |
|----|----------|-------------|----------------------|
| F1 | Écoute HTTP | Accepter requêtes HTTP sur port configurable | Le serveur écoute sur le port spécifié (défaut: 8888) |
| F2 | Tunnel HTTPS | Accepter requêtes HTTPS via méthode CONNECT | Les requêtes CONNECT établissent un tunnel TCP |
| F3 | Routage Webshare | Router vers Webshare avec authentification | Requêtes transmises à Webshare avec auth Basic |
| F4 | Proxy corporate | Support optionnel proxy corporate (double tunneling) | Tunnel: client → corporate → webshare → target |
| F5 | Toggle corporate | Option CLI pour activer/désactiver proxy corporate | `--no-corporate` désactive le proxy corporate |
| F6 | Configuration YAML | Configuration via fichier YAML | Lecture et parsing du fichier config.yaml |
| F7 | Variables d'env | Support variables d'environnement pour credentials | `${VAR}` remplacé par valeur de VAR |

### 4.2 Quality Features (Should Have)

| ID | Exigence | Description | Critère d'acceptation |
|----|----------|-------------|----------------------|
| F8 | Logging | Logs des requêtes avec niveau configurable | Logs formatés avec timestamp, niveau, message |
| F9 | Graceful shutdown | Arrêt propre sur Ctrl+C (tous OS) et SIGTERM (Unix) | Connexions actives terminées proprement |
| F10 | Config validation | Validation de la configuration au démarrage | Erreurs claires si config invalide |

### 4.3 Future Features (Won't Have v1)

| ID | Feature | Raison d'exclusion |
|----|---------|-------------------|
| F11 | Métriques Prometheus | Complexité ajoutée, v2 |
| F12 | API REST admin | Non essentiel pour v1 |
| F13 | Health checks auto | Nécessite gestion état, v2 |
| F14 | Retry avec backoff | Complexité, v2 |
| F15 | Support SOCKS5 | Webshare utilise HTTP |
| F16 | Cache réponses | Hors scope proxy |
| F17 | Load balancing | Single proxy rotatif suffit |

---

## 5. Exigences Non-Fonctionnelles

### 5.1 Performance

| ID | Exigence | Critère | Méthode de mesure |
|----|----------|---------|-------------------|
| NF1 | Latence | < 50ms ajoutée par Mooltiroute | Benchmark curl avec/sans proxy |
| NF2 | Connexions | ≥ 100 connexions simultanées | Test de charge avec wrk/ab |
| NF3 | Démarrage | < 1 seconde | Time de lancement CLI |
| NF4 | Mémoire | < 50 MB au repos | Mesure RSS process |

### 5.2 Sécurité

| ID | Exigence | Description |
|----|----------|-------------|
| NF5 | Credentials non loggés | Jamais de mot de passe en clair dans les logs |
| NF6 | Bind localhost | Par défaut, écoute uniquement sur 127.0.0.1 |
| NF7 | Pas de stockage credentials | Credentials lus depuis env vars ou config |

### 5.3 Compatibilité

| ID | Exigence | Description |
|----|----------|-------------|
| NF8 | Python 3.10+ | Utilisation des features modernes (type hints, match) |
| NF9 | OS | Linux, macOS, Windows (natif et WSL) |
| NF10 | Dépendances | Minimales (pyyaml uniquement) |

### 5.4 Maintenabilité

| ID | Exigence | Description |
|----|----------|-------------|
| NF11 | Code modulaire | Séparation claire des responsabilités |
| NF12 | Type hints | Annotations de type sur toutes les fonctions |
| NF13 | Docstrings | Documentation des modules et fonctions publiques |

---

## 6. Contraintes

### 6.1 Contraintes Techniques

- **Asyncio obligatoire** : Pour gérer les connexions concurrentes efficacement
- **Pas de framework web** : Trop lourd pour un simple proxy
- **Dépendance unique** : Seulement pyyaml pour parser la config

### 6.2 Contraintes Business

- **Webshare uniquement** : Pas de support multi-provider en v1
- **Pas d'UI** : CLI uniquement
- **Open source** : Code public sur GitHub

---

## 7. Métriques de Succès

| Métrique | Objectif | Méthode de mesure |
|----------|----------|-------------------|
| Temps de setup | < 5 minutes | Test utilisateur |
| Taux d'erreur | < 0.1% des requêtes | Logs d'erreur |
| Latence p99 | < 100ms ajoutée | Benchmark |
| Adoption | Utilisé quotidiennement | Feedback utilisateur |

---

## 8. Risques et Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Webshare indisponible | Faible | Élevé | Logs clairs, fail fast |
| Proxy corporate bloque Webshare | Moyen | Élevé | Mode --no-corporate, documentation |
| Performance insuffisante | Faible | Moyen | Asyncio, benchmarks réguliers |
| Credentials exposés | Faible | Élevé | Env vars, sanitization logs |

---

## 9. Timeline

| Phase | Durée | Livrables |
|-------|-------|-----------|
| v1.0 - Core | ✅ Terminé | Proxy HTTP/HTTPS, double tunneling, config YAML |
| v1.1 - Stabilisation | À venir | Tests, documentation, bugfixes |
| v2.0 - Observabilité | Futur | Métriques Prometheus, health checks |

---

## 10. Glossaire

| Terme | Définition |
|-------|------------|
| **CONNECT** | Méthode HTTP pour établir un tunnel TCP (utilisée pour HTTPS via proxy) |
| **Double tunneling** | Passage par deux proxies successifs (corporate → webshare) |
| **Proxy rotatif** | Service proxy qui change automatiquement d'IP à chaque requête |
| **Webshare** | Fournisseur de proxies rotatifs |
| **Rate limiting** | Limitation du nombre de requêtes acceptées par période |

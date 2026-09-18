# GeminiUsageDashboard

Dashboard Streamlit public (avec accès protégé par mot de passe) pour visualiser les coûts d'utilisation estimés de l'API Google Gemini Developer API.

Ce dashboard agit exclusivement comme un client frontal consommant les endpoints FastAPI de **GeminiUsageMonitor** déployé sur Railway via HTTPS.

## Architecture

- **Frontend** : Streamlit (hébergeable sur Streamlit Community Cloud).
- **Backend distant** : API FastAPI hébergée sur Railway (HTTPS).
- **Sécurité** :
  - Accès au dashboard filtré par un mot de passe (`DASHBOARD_PASSWORD`) comparé en temps constant (`hmac.compare_digest`).
  - **Aucun appel réseau** vers le backend n'est émis avant authentification réussie.
  - Aucune connexion directe à la base de données PostgreSQL / Neon.
  - Aucun secret durci dans le code source.

## Configuration & Secrets

Trois variables sont requises pour exécuter l'application :

| Variable | Description |
|---|---|
| `MONITOR_API_URL` | URL HTTPS racine du backend FastAPI (ex: `https://votre-service.up.railway.app`) |
| `MONITOR_READ_TOKEN` | Jeton de lecture transmis dans l'en-tête `X-Monitor-Read-Token` |
| `DASHBOARD_PASSWORD` | Mot de passe requis pour déverrouiller l'interface utilisateur |

> ⚠️ **Sécurité** : Ne jamais committer `.streamlit/secrets.toml` ni `.env` dans Git. Le fichier `.gitignore` les exclut par défaut.

## Lancement local

1. Cloner le dépôt et installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

2. Configurer les secrets locaux :
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   Renseignez vos vraies valeurs dans `.streamlit/secrets.toml`.

3. Lancer l'application Streamlit :
   ```bash
   streamlit run app.py
   ```

4. Exécuter les tests :
   ```bash
   pytest
   ```

## Déploiement sur Streamlit Community Cloud

1. Déposer ce repo sur GitHub : `cdurand42/GeminiUsageDashboard`.
2. Connecter le repo sur [Streamlit Community Cloud](https://share.streamlit.io/) :
   - **Repository** : `cdurand42/GeminiUsageDashboard`
   - **Branch** : `main`
   - **Main file path** : `app.py`
3. Dans les **Advanced Settings** > **Secrets** de l'application Streamlit Cloud, renseigner :
   ```toml
   MONITOR_API_URL = "https://votre-service.up.railway.app"
   MONITOR_READ_TOKEN = "votre-token-de-lecture"
   DASHBOARD_PASSWORD = "votre-mot-de-passe-robuste"
   ```
4. Déployer l'application.

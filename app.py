"""Streamlit Dashboard for GeminiUsageMonitor.

Independent operational dashboard monitoring estimated Google Gemini API usage costs.
Connects securely to the GeminiUsageMonitor FastAPI backend via HTTPS.
Protected by a password gate to keep access private on public hosting.
"""

from decimal import Decimal
import hmac
import os
from typing import Any
import pandas as pd
import requests
import streamlit as st


def get_config(key: str, default: str = "") -> str:
    """Retrieve configuration from st.secrets first, falling back to environment variables."""
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            val = st.secrets[key]
            if val is not None and str(val).strip():
                return str(val).strip()
    except Exception:
        pass
    env_val = os.getenv(key, default)
    return env_val.strip() if env_val else default


def verify_password(input_password: str, expected_password: str) -> bool:
    """Safely compare passwords using constant-time comparison to prevent timing attacks."""
    if not input_password or not expected_password:
        return False
    return hmac.compare_digest(input_password.encode("utf-8"), expected_password.encode("utf-8"))


def make_api_request(
    api_url: str,
    endpoint: str,
    read_token: str = "",
    params: dict[str, Any] | None = None,
    timeout: int = 10,
) -> tuple[Any | None, str | None]:
    """Centralized HTTP GET request helper for the GeminiUsageMonitor API.

    Returns:
        tuple (data, error_message):
            - On success: (json_data, None)
            - On failure: (None, user_facing_error_string)
    Never exposes read tokens or raw tracebacks in error messages.
    """
    if not api_url:
        return None, "Configuration manquante : MONITOR_API_URL n'est pas configuré."

    base = api_url.rstrip("/")
    url = f"{base}{endpoint}"
    headers = {}
    if read_token:
        headers["X-Monitor-Read-Token"] = read_token

    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        if response.status_code == 401:
            return None, "Accès non autorisé (401) : le jeton MONITOR_READ_TOKEN est invalide ou manquant."
        if response.status_code == 403:
            return None, "Accès interdit (403) : permissions insuffisantes pour accéder à cette ressource."
        if response.status_code == 404:
            return None, f"Ressource non trouvée (404) sur le backend (`{endpoint}`)."
        if response.status_code >= 500:
            return None, f"Erreur interne du serveur ({response.status_code}) sur le backend GeminiUsageMonitor."
        response.raise_for_status()
        try:
            return response.json(), None
        except ValueError:
            return None, "Réponse invalide reçue du backend GeminiUsageMonitor (format JSON attendu)."
    except requests.exceptions.Timeout:
        return None, "Délai d'attente dépassé lors de la communication avec le backend GeminiUsageMonitor."
    except requests.exceptions.ConnectionError:
        return None, "Backend GeminiUsageMonitor indisponible (connexion impossible)."
    except requests.exceptions.RequestException:
        return None, "Backend GeminiUsageMonitor indisponible."


def format_currency(val: Any) -> str:
    """Format USD amount with appropriate decimal precision."""
    if val is None:
        return "Non chiffré"
    try:
        dec = Decimal(str(val))
    except Exception:
        return "Non chiffré"
    if dec == Decimal("0"):
        return "$ 0.0000"
    if dec < Decimal("0.01"):
        return f"$ {dec:.6f}"
    return f"$ {dec:.4f}"


def render_login(expected_password: str) -> None:
    """Render the minimal login form for unauthenticated users."""
    st.title("Gemini Usage Monitor")
    st.caption("Accès restreint. Veuillez saisir le mot de passe pour continuer.")

    with st.form("login_form", clear_on_submit=False):
        password_input = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Connexion")
        if submitted:
            if verify_password(password_input, expected_password):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")


def main() -> None:
    """Main application routine with strict password gate and dashboard rendering."""
    st.set_page_config(
        page_title="Gemini Usage Monitor",
        page_icon="📊",
        layout="wide",
    )

    # 1. Password Gate (Fail-Closed)
    expected_password = get_config("DASHBOARD_PASSWORD")
    if not expected_password:
        st.title("Gemini Usage Monitor")
        st.error("Configuration d'accès manquante.")
        st.stop()

    if not st.session_state.get("authenticated", False):
        render_login(expected_password)
        st.stop()

    # 2. Authenticated Session: Sidebar controls
    with st.sidebar:
        st.markdown("### Session")
        if st.button("Déconnexion"):
            st.session_state["authenticated"] = False
            st.rerun()

    # 3. Backend Configuration Check
    api_url = get_config("MONITOR_API_URL")
    read_token = get_config("MONITOR_READ_TOKEN")

    if not api_url:
        st.title("Gemini Usage Monitor")
        st.error("Configuration manquante : MONITOR_API_URL n'est pas configuré.")
        st.stop()

    if not read_token:
        st.title("Gemini Usage Monitor")
        st.error("Configuration manquante : MONITOR_READ_TOKEN n'est pas configuré.")
        st.stop()

    # 4. API Connectivity Check (Public health check)
    health_data, health_err = make_api_request(api_url, "/health", timeout=5)
    if health_err or not health_data or health_data.get("status") != "ok":
        st.title("Gemini Usage Monitor")
        st.error("Backend GeminiUsageMonitor indisponible.")
        st.stop()

    def fetch_api(endpoint: str, params: dict[str, Any] | None = None) -> Any | None:
        data, err = make_api_request(api_url, endpoint, read_token=read_token, params=params, timeout=10)
        if err:
            st.error(err)
            return None
        return data

    app_version = health_data.get("version", "inconnu")
    db_backend = health_data.get("database_backend", "inconnu")

    # --- Header & Badges ---
    st.title("Gemini Usage Monitor")

    col_info1, col_info2, col_info3 = st.columns([3, 1, 1])
    with col_info1:
        st.caption(
            "Monitoring indépendant des coûts estimés d'utilisation de l'API Google Gemini Developer API par projet"
        )
    with col_info2:
        st.caption(f"🟢 **API connectée** (v{app_version})")
    with col_info3:
        st.caption(f"💾 **Base** : `{db_backend}`")

    # --- Summary Metrics ---
    summary = fetch_api("/summary")
    if summary:
        unpriced = summary.get("unpriced_calls", 0)
        partial = summary.get("partial_calls", 0)
        complete = summary.get("complete_calls", 0)
        total_calls = summary.get("total_calls", 0)

        if unpriced > 0:
            st.error(
                f"⚠️ **Appels non chiffrés** : {unpriced} appel(s) n'ont pas pu être chiffrés "
                f"(modèle inconnu, mauvaise plateforme ou métadonnées incomplètes). "
                "Le montant total ci-dessous ne les inclut pas."
            )
        if partial > 0:
            st.warning(
                f"ℹ️ **Coûts partiels** : {partial} appel(s) comportent un coût partiel "
                "(les tokens sont chiffrés, mais les requêtes payantes Google Search/Maps Grounding "
                "ne sont pas incluses)."
            )

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric(
                label="Coût estimé aujourd'hui",
                value=format_currency(summary.get("today_cost_usd")),
            )
        with col2:
            st.metric(
                label="Coût estimé sur 7 jours",
                value=format_currency(summary.get("last_7_days_cost_usd")),
            )
        with col3:
            st.metric(
                label="Coût estimé total",
                value=format_currency(summary.get("total_cost_usd")),
            )
        with col4:
            st.metric(
                label="Appels complets",
                value=f"{complete:,} / {total_calls:,}",
            )
        with col5:
            st.metric(
                label="Partiels / Non chiffrés",
                value=f"{partial} partiel(s) | {unpriced} non chiffré(s)",
            )

    st.markdown("---")

    # --- Section 1: Par projet ---
    st.subheader("Par projet")
    projects = fetch_api("/projects") or []

    if not projects:
        st.info("Aucun projet enregistré pour le moment. Envoyez des événements sur `POST /usage`.")
    else:
        project_rows = []
        for p in projects:
            p_summary = fetch_api("/summary", params={"project": p})
            if p_summary:
                project_rows.append({
                    "Projet": p,
                    "Aujourd'hui": format_currency(p_summary.get("today_cost_usd")),
                    "7 jours": format_currency(p_summary.get("last_7_days_cost_usd")),
                    "Total estimé": format_currency(p_summary.get("total_cost_usd")),
                    "Appels": p_summary.get("total_calls", 0),
                    "Complets": p_summary.get("complete_calls", 0),
                    "Partiels": p_summary.get("partial_calls", 0),
                    "Non chiffrés": p_summary.get("unpriced_calls", 0),
                })

        if project_rows:
            df_projects = pd.DataFrame(project_rows)
            st.dataframe(df_projects, use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- Section 2: Par modèle ---
    st.subheader("Par modèle")
    model_breakdown = fetch_api("/breakdown/models") or []

    if not model_breakdown:
        st.info("Aucune donnée de modèle disponible.")
    else:
        model_rows = []
        for m in model_breakdown:
            model_rows.append({
                "Modèle": m.get("model", "-"),
                "Appels": m.get("calls", 0),
                "Input tokens": f"{m.get('prompt_tokens', 0):,}",
                "Output tokens": f"{m.get('output_tokens', 0):,}",
                "Cached tokens": f"{m.get('cached_tokens', 0):,}",
                "Coût estimé": format_currency(m.get("estimated_cost_usd")),
                "Complets": m.get("complete_calls", 0),
                "Partiels": m.get("partial_calls", 0),
                "Non chiffrés": m.get("unpriced_calls", 0),
            })
        df_models = pd.DataFrame(model_rows)
        st.dataframe(df_models, use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- Section 3: Historique ---
    st.subheader("Historique des événements récents")

    filter_col1, filter_col2 = st.columns([2, 1])
    with filter_col1:
        project_options = ["Tous les projets"] + projects
        selected_project = st.selectbox("Filtrer par projet :", project_options)
    with filter_col2:
        events_limit = st.selectbox("Nombre d'événements :", [25, 50, 100, 200], index=1)

    req_params: dict[str, Any] = {"limit": events_limit}
    if selected_project != "Tous les projets":
        req_params["project"] = selected_project

    events = fetch_api("/events", params=req_params) or []

    if not events:
        st.info("Aucun événement à afficher pour ce filtre.")
    else:
        event_rows = []
        for ev in events:
            status_label = ev.get("cost_status", "unknown")
            if status_label == "complete":
                cost_display = f"Complet : {format_currency(ev.get('estimated_cost_usd'))}"
            elif status_label == "partial":
                cost_display = f"Partiel : {format_currency(ev.get('estimated_cost_usd'))} [Grounding]"
            else:
                cost_display = f"Non chiffré ({status_label})"

            event_rows.append({
                "Date (UTC)": str(ev.get("timestamp", ""))[:19].replace("T", " "),
                "Projet": ev.get("project", "-"),
                "Modèle": ev.get("model", "-"),
                "Opération": ev.get("operation", "-"),
                "Prompt": ev.get("prompt_tokens", 0),
                "Output": ev.get("output_tokens", 0),
                "Thoughts": ev.get("thoughts_tokens", 0),
                "Images": ev.get("generated_image_count", 0),
                "Total tokens": ev.get("total_tokens", 0),
                "Coût & Statut": cost_display,
                "Période / Version": ev.get("pricing_period_id") or ev.get("pricing_version") or "-",
                "ID Événement": ev.get("event_id") or f"#{ev.get('id', '-')}",
            })
        df_events = pd.DataFrame(event_rows)
        st.dataframe(df_events, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption(
        "ℹ️ **Avertissement** : Les coûts affichés sont des estimations calculées selon la grille "
        "officielle Google Gemini Developer API. "
        "Ils ne constituent pas une facture officielle Google Cloud et n'intègrent pas les requêtes de Grounding payantes."
    )


if __name__ == "__main__":
    main()

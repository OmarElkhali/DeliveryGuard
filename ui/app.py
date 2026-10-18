import csv
import hashlib
import io
import json

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from deliveryguard.config import settings
from deliveryguard.quality import FIELDS
from deliveryguard.synthetic import generate

st.set_page_config(page_title="DeliveryGuard", page_icon="📦", layout="wide")
config = settings()
st.markdown(
    """<style>
.block-container {max-width:1200px;padding-top:2rem}
h1,h2,h3 {letter-spacing:-.025em}
[data-testid=stMetric] {background:#eef3f5;padding:1rem;border-radius:8px}
</style>""",
    unsafe_allow_html=True,
)
st.sidebar.title("DeliveryGuard")
st.sidebar.caption("v0.1.0 · Pilote local")
key = "" if config.demo else st.sidebar.text_input("Clé API de l'entreprise", type="password")
page = st.sidebar.radio(
    "Espace de travail",
    [
        "Démonstration",
        "Import et mapping",
        "Qualité",
        "Analyse des livraisons",
        "Modèles et évaluation",
        "Commandes à surveiller",
    ],
)
st.sidebar.divider()
st.sidebar.caption("Omar Elkhali · ENSAM Casablanca\n\nLes données restent sur cette instance.")
if config.demo:
    st.warning(
        "MODE DÉMONSTRATION — Données synthétiques uniquement. Ne chargez aucune donnée réelle."
    )
elif not key:
    st.title("DeliveryGuard")
    st.info(
        "Saisissez la clé API dans la barre latérale pour accéder aux données de votre entreprise."
    )
    st.stop()


def api(method, path, **kwargs):
    try:
        response = requests.request(
            method, config.api_url + path, headers={"X-API-Key": key}, timeout=60, **kwargs
        )
        if not response.ok:
            try:
                error = response.json()["error"]
                message = f"{error['message']} ({error['code']})"
                if error.get("details"):
                    message += " — " + str(error["details"])
            except (ValueError, KeyError):
                message = f"Service indisponible (HTTP {response.status_code})"
            st.error(message)
            st.stop()
        return response
    except requests.RequestException:
        st.error("API inaccessible. Vérifiez le service API, son URL et le réseau local.")
        st.stop()


def show_quality(result):
    cols = st.columns(4)
    for col, label, field in zip(
        cols,
        ["Lignes", "Valides", "Rejetées", "Livraisons observées"],
        ["total", "valid", "rejected", "observable"],
        strict=True,
    ):
        col.metric(label, result[field])
    for item in result["warnings"]:
        st.info(item)
    if result["issues"]:
        st.dataframe(result["issues"], hide_index=True, width="stretch")
        with st.expander("Exemples et motifs de rejet"):
            st.json(result["examples"])
    else:
        st.success("Aucune incohérence détectée par les règles v0.1.")


if page == "Démonstration":
    st.title("Anticiper les retards. Comprendre les données.")
    st.write(
        "Importez vos historiques, contrôlez leur qualité et classez les nouvelles commandes par risque de retard."
    )
    st.caption(
        "Une instance, une entreprise. Sans compte externe ni envoi de données à un service tiers."
    )
    st.subheader("Un parcours vérifiable, en cinq étapes")
    st.markdown(
        "1. Importer et auditer\n2. Analyser les livraisons observées\n3. Entraîner dans le worker local\n4. Examiner et activer une version\n5. Classer les commandes à surveiller"
    )
    st.info(
        "L'exemple contient 1 500 commandes entièrement synthétiques, générées avec la graine 42. Ses scores ne prouvent aucune performance réelle."
    )
    st.download_button("Télécharger le CSV synthétique", generate(), "synthetic.csv", "text/csv")
    if st.button("Charger la démonstration", type="primary"):
        with st.spinner("Audit et import des données synthétiques…"):
            result = api(
                "POST", "/imports", files={"file": ("synthetic.csv", generate(), "text/csv")}
            ).json()
        st.session_state["import_id"] = result["id"]
        st.success(
            f"Import terminé : {result['valid']} lignes valides. Ouvrez Qualité, puis Modèles et évaluation."
        )
        show_quality(result)
elif page == "Import et mapping":
    st.title("Import et mapping")
    st.write(
        "CSV UTF-8 à virgules, 5 Mio maximum. Dates ISO 8601 ; sans fuseau = UTC. Supprimez toute colonne personnelle ou hors schéma."
    )
    uploaded = st.file_uploader("Historique de livraison", type=["csv"])
    if uploaded:
        raw = uploaded.getvalue()
        if len(raw) > config.max_upload_bytes:
            st.error("Fichier trop volumineux")
            st.stop()
        try:
            header = next(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
            if not header or len(set(header)) != len(header) or len(header) > len(FIELDS):
                raise ValueError()
        except (UnicodeError, csv.Error, StopIteration, ValueError):
            st.error(
                "En-tête CSV invalide ou trop de colonnes. Vérifiez le format et retirez les données personnelles."
            )
            st.stop()
        mapping = {}
        for col in header:
            mapping[col] = st.selectbox(
                f"Colonne {col}",
                FIELDS,
                index=FIELDS.index(col) if col in FIELDS else 0,
                key=f"map_{col}",
            )
        update = st.checkbox("Autoriser le remplacement explicite des commandes existantes")
        st.caption(
            "Sans cette option, seules les nouvelles commandes et les lignes identiques sont acceptées. Une issue terminée ne peut pas redevenir ouverte."
        )
        token = hashlib.sha256(
            raw + json.dumps([mapping, update], sort_keys=True).encode()
        ).hexdigest()
        if st.button("Prévisualiser et auditer", type="primary"):
            result = api(
                "POST",
                "/imports/preview",
                files={"file": ("history.csv", raw, "text/csv")},
                data={"mapping": json.dumps(mapping), "update": str(update).lower()},
            ).json()
            st.session_state["preview"] = (token, result)
        preview = st.session_state.get("preview")
        if preview and preview[0] == token:
            show_quality(preview[1])
            with st.expander("Aperçu des 10 premières lignes sources"):
                try:
                    st.dataframe(pd.read_csv(io.BytesIO(raw), nrows=10, dtype=str), hide_index=True)
                except ValueError:
                    st.error("Aperçu indisponible")
            st.caption(
                "La validation importe seulement les lignes acceptées. Le fichier source et les rejets sont conservés dans le volume privé."
            )
            if st.button("Valider l'import", disabled=preview[1]["valid"] == 0):
                result = api(
                    "POST",
                    "/imports",
                    files={"file": ("history.csv", raw, "text/csv")},
                    data={"mapping": json.dumps(mapping), "update": str(update).lower()},
                ).json()
                st.session_state["import_id"] = result["id"]
                if result["reused"]:
                    st.info(
                        "Import enregistré précédemment : reçu initial retrouvé, aucune écriture rejouée."
                    )
                else:
                    st.success(
                        f"Import enregistré : {result['inserted']} créations, {result['updated']} mises à jour, {result['unchanged']} inchangées, {result['rejected']} rejetées."
                    )
elif page == "Qualité":
    st.title("Qualité des données")
    items = api("GET", "/imports").json()
    if not items:
        st.info("Aucun import. Chargez la démonstration ou un CSV historique.")
    else:
        ids = [i["id"] for i in items]
        chosen = st.selectbox(
            "Import à examiner",
            ids,
            index=ids.index(st.session_state["import_id"])
            if st.session_state.get("import_id") in ids
            else 0,
        )
        result = api("GET", f"/imports/{chosen}/quality").json()
        show_quality(result)
        st.download_button(
            "Télécharger les lignes rejetées et leurs motifs",
            api("GET", f"/imports/{chosen}/rejected").content,
            "rejected.csv",
            "text/csv",
        )
elif page == "Analyse des livraisons":
    st.title("Analyse des livraisons")
    result = api("GET", "/analytics/summary").json()
    if not result["total"]:
        st.info("Importez des commandes pour commencer l'analyse.")
    else:
        cols = st.columns(4)
        cols[0].metric("Commandes", result["total"])
        cols[1].metric("Livrées", result["observed"])
        cols[2].metric("Retards observés", result["late"])
        cols[3].metric(
            "Taux parmi les livraisons",
            f"{result['late_rate']:.1%}" if result["late_rate"] is not None else "Non calculable",
        )
        st.caption(result["warning"])
        st.plotly_chart(
            px.bar(
                pd.DataFrame([{"Statut": k, "Commandes": v} for k, v in result["counts"].items()]),
                x="Statut",
                y="Commandes",
                text_auto=True,
                color_discrete_sequence=["#244d65"],
            ),
            width="stretch",
        )
        if result["late_by_carrier"]:
            st.plotly_chart(
                px.bar(
                    pd.DataFrame(result["late_by_carrier"]),
                    x="carrier",
                    y="late",
                    labels={"carrier": "Transporteur", "late": "Nombre de retards observés"},
                    text_auto=True,
                    color_discrete_sequence=["#ab782a"],
                ),
                width="stretch",
            )
        st.download_button(
            "Exporter les commandes pour Power BI",
            api("GET", "/exports/orders.csv").content,
            "orders.csv",
            "text/csv",
        )
elif page == "Modèles et évaluation":
    st.title("Modèles et évaluation")
    if st.session_state.pop("model_activated", False):
        st.success("Version activée explicitement")
    st.info(
        "Prédiction au moment de la commande. Split chronologique 60/20/20 avec purge des issues indisponibles. Le test final ne sert ni au choix du modèle ni au seuil."
    )
    if st.button("Créer un entraînement", type="primary"):
        run = api("POST", "/training-runs").json()
        st.success(f"Entraînement en attente : {run['id']}. Le worker doit être démarré.")
    if st.button("Actualiser les entraînements"):
        st.rerun()
    runs = api("GET", "/models").json()
    if not runs:
        st.info("Aucun entraînement. Importez des données puis créez un entraînement.")
    else:
        selected = st.selectbox("Version", [r["id"] for r in runs])
        run = api("GET", f"/training-runs/{selected}").json()
        active = next(r["active"] for r in runs if r["id"] == selected)
        st.write(f"État : **{run['status']}** · Modèle actif : **{'Oui' if active else 'Non'}**")
        report = run["report"]
        if run["status"] in ["queued", "running"]:
            st.info(
                "Traitement en attente ou en cours. Cliquez sur Actualiser. CLI : deliveryguard worker"
            )
        elif run["status"] == "failed":
            st.error(report.get("message", "Échec contrôlé"))
        else:
            st.caption(
                f"Modèle : {report['selected']} · Seuil : {report['threshold']:.3f} · Score non calibré"
            )
            st.dataframe(
                pd.DataFrame(
                    {
                        "Validation": {
                            k: v for k, v in report["validation"].items() if k != "confusion_matrix"
                        },
                        "Test final": {
                            k: v for k, v in report["test"].items() if k != "confusion_matrix"
                        },
                    }
                ),
                width="stretch",
            )
            st.subheader("Matrice de confusion — test final")
            st.dataframe(
                pd.DataFrame(
                    report["test"]["confusion_matrix"],
                    index=["Réel : à l'heure", "Réel : retard"],
                    columns=["Prédit : à l'heure", "Prédit : retard"],
                )
            )
            st.subheader("Périodes et effectifs")
            st.json(report["splits"])
            st.subheader("Associations observées sur validation")
            st.caption("Importance par permutation; aucune interprétation causale.")
            st.dataframe(report["associations"], hide_index=True)
            for limit in report["limitations"]:
                st.write("• " + limit)
            st.info(report["activation_reason"])
            reviewed = st.checkbox("J'ai examiné les métriques, les périodes et les limites")
            if st.button(
                "Activer cette version",
                disabled=not reviewed or not report["activation_allowed"] or active,
            ):
                api("POST", f"/models/{selected}/activate", json={"reviewed_limits": True})
                st.session_state["model_activated"] = True
                st.rerun()
            with st.expander("Fiche complète de cet entraînement"):
                st.json(run)
else:
    st.title("Commandes à surveiller")
    result = api("GET", "/analytics/summary").json()
    st.subheader(f"Alertes opérationnelles : {result['overdue_count']} promesses dépassées")
    st.caption("Constat sur les commandes ouvertes. Ces alertes sont indépendantes du modèle ML.")
    if result["overdue"]:
        st.dataframe(result["overdue"], hide_index=True)
    else:
        st.info("Aucune commande ouverte avec promesse dépassée.")
    st.subheader("Classement ML au moment de la commande")
    st.caption(
        "CSV des nouvelles commandes : order_id, ordered_at, promised_delivery_at et variables facultatives. Ni status, ni delivered_at. Maximum 1 000 lignes."
    )
    example = "order_id,ordered_at,promised_delivery_at,carrier,destination_zone\nNEW-001,2026-01-01T10:00:00Z,2026-01-03T10:00:00Z,Régional,Rural\n".encode()
    st.download_button("Exemple de commandes à classer", example, "new_orders.csv", "text/csv")
    upload_file = st.file_uploader(
        "Nouvelles commandes à classer",
        type=["csv"],
        on_change=lambda: st.session_state.pop("predictions", None),
    )
    if upload_file and st.button("Calculer les risques", type="primary"):
        if upload_file.size > config.max_upload_bytes:
            st.error("Fichier trop volumineux")
            st.stop()
        try:
            data = list(csv.DictReader(io.StringIO(upload_file.getvalue().decode("utf-8-sig"))))
            data = [{k: v or None for k, v in row.items()} for row in data]
        except (ValueError, UnicodeError, csv.Error):
            st.error("CSV invalide")
            st.stop()
        prediction = api("POST", "/predict/batch", json={"orders": data}).json()
        st.session_state["predictions"] = prediction
    if "predictions" in st.session_state:
        prediction = st.session_state["predictions"]
        st.caption(f"Version {prediction['model_id']} · {prediction['score_note']}")
        st.dataframe(prediction["predictions"], hide_index=True)
        from deliveryguard.quality import csv_bytes

        st.download_button(
            "Exporter le classement",
            csv_bytes(
                [
                    {
                        **row,
                        "model_id": prediction["model_id"],
                        "threshold": prediction["threshold"],
                    }
                    for row in prediction["predictions"]
                ]
            ),
            "risk_scores.csv",
            "text/csv",
        )

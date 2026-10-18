"""Build README figures from a verified synthetic demo or its saved evaluation snapshot."""

import argparse
import hashlib
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
from playwright.sync_api import expect, sync_playwright

from deliveryguard.synthetic import generate

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "results"
INK, TEAL, AMBER = "#244d65", "#227c83", "#ae7625"


def snapshot(api):
    client = requests.Session()

    def get(path):
        response = client.get(api + path, timeout=30)
        response.raise_for_status()
        return response

    assert get("/health/live").json()["demo"], "Report capture is restricted to synthetic demo mode"
    expected = pd.read_csv(io.BytesIO(generate()))
    actual = pd.read_csv(io.BytesIO(get("/exports/orders.csv").content))
    for frame in [expected, actual]:
        for column in ["ordered_at", "promised_delivery_at", "delivered_at"]:
            frame[column] = pd.to_datetime(frame[column], format="mixed", utc=True).astype(
                "datetime64[ns, UTC]"
            )
    pd.testing.assert_frame_equal(
        actual[expected.columns].sort_values("order_id").reset_index(drop=True),
        expected.sort_values("order_id").reset_index(drop=True),
    )
    run = next(r for r in get("/models").json() if r["active"])
    assert run["status"] == "succeeded"
    orders = pd.read_csv(ROOT / "examples" / "new_orders.csv").to_dict("records")
    response = client.post(api + "/predict/batch", json={"orders": orders}, timeout=30)
    response.raise_for_status()
    summary = get("/analytics/summary").json()
    result = {
        "origin": "Synthetic DeliveryGuard generator, 1500 rows, seed 42; source equality verified",
        "captured_at": datetime.now(UTC).isoformat(),
        "generator_sha256": hashlib.sha256(generate()).hexdigest(),
        "orders": summary["total"],
        "counts": summary["counts"],
        "observed": summary["observed"],
        "late": summary["late"],
        "late_rate": summary["late_rate"],
        "run_id": run["id"],
        "run_created_at": run["created_at"],
        "report": run["report"],
        "example_predictions": response.json(),
    }
    assert result["orders"] == 1500 and result["observed"] == 1376 and result["late"] == 397
    return result


def figures(data):
    report = data["report"]
    parts = [report["splits"][key] for key in ["train", "validation", "test"]]
    split = go.Figure(
        [
            go.Bar(
                name="Observed on time",
                x=["Train", "Validation", "Final test"],
                y=[p["n"] - p["late"] for p in parts],
                marker_color=INK,
                text=[p["n"] - p["late"] for p in parts],
                textposition="inside",
            ),
            go.Bar(
                name="Observed late",
                x=["Train", "Validation", "Final test"],
                y=[p["late"] for p in parts],
                marker_color=AMBER,
                text=[p["late"] for p in parts],
                textposition="inside",
            ),
        ]
    )
    split.update_layout(barmode="stack", yaxis_title="Delivered orders")

    names = {
        "dummy": "Dummy baseline",
        "logistic_C0.1": "Logistic regression · C=0.1",
        "logistic_C1": "Logistic regression · C=1",
        "forest_depth5": "Random Forest · depth 5 (selected)",
        "forest_depth10": "Random Forest · depth 10",
    }
    candidates = sorted(report["candidates"], key=lambda c: c["validation_average_precision"])
    comparison = go.Figure(
        go.Bar(
            x=[c["validation_average_precision"] for c in candidates],
            y=[names[c["name"]] for c in candidates],
            orientation="h",
            text=[f"{c['validation_average_precision']:.4f}" for c in candidates],
            textposition="outside",
            marker_color=[TEAL if c["name"] == report["selected"] else INK for c in candidates],
        )
    )
    comparison.update_layout(
        xaxis_title="Average precision · validation only",
        xaxis_range=[0, 1],
        margin={"l": 370, "r": 90, "t": 110, "b": 120},
    )

    matrix = report["test"]["confusion_matrix"]
    confusion = go.Figure(
        go.Heatmap(
            z=matrix,
            x=["Predicted on time", "Predicted late"],
            y=["Actually on time", "Actually late"],
            showscale=False,
            colorscale=[[0, "#eaf1f5"], [1, INK]],
            zmin=0,
        )
    )
    for row in range(2):
        for column in range(2):
            confusion.add_annotation(
                x=column,
                y=row,
                text=str(matrix[row][column]),
                showarrow=False,
                font={"size": 48, "color": "white" if matrix[row][column] > 55 else INK},
            )
    confusion.update_layout(
        yaxis_autorange="reversed", margin={"l": 220, "r": 90, "t": 110, "b": 130}
    )

    metric_keys = ["precision", "recall", "f1", "average_precision", "roc_auc"]
    metric_labels = ["Precision", "Recall", "F1", "Average precision", "ROC-AUC"]
    metrics = go.Figure(
        [
            go.Bar(
                name=label,
                x=metric_labels,
                y=[report[part][key] for key in metric_keys],
                text=[f"{report[part][key]:.3f}" for key in metric_keys],
                textposition="outside",
                marker_color=color,
            )
            for part, label, color in [
                ("validation", "Validation", INK),
                ("test", "Final test", TEAL),
            ]
        ]
    )
    metrics.update_layout(barmode="group", yaxis_range=[0, 1.08], yaxis_title="Metric value")

    associations = sorted(report["associations"], key=lambda a: a["mean"])
    importance = go.Figure(
        go.Bar(
            x=[a["mean"] for a in associations],
            y=[a["feature"] for a in associations],
            orientation="h",
            marker_color=INK,
            error_x={"type": "data", "array": [a["std"] for a in associations]},
        )
    )
    importance.update_layout(
        xaxis_title="Decrease in validation average precision after permutation",
        margin={"l": 260, "r": 90, "t": 110, "b": 130},
    )
    return [
        (
            "01-chronological-split.png",
            split,
            "Chronological evaluation · observed deliveries only",
            "Synthetic seed 42 · 21 unavailable outcomes purged · open/cancelled orders excluded",
        ),
        (
            "02-model-comparison.png",
            comparison,
            "Five candidates · selection uses validation only",
            "Synthetic seed 42 · the final test is not used to choose the model",
        ),
        (
            "03-confusion-matrix.png",
            confusion,
            "Final test · 276 orders · fixed threshold 0.20",
            "Synthetic seed 42 · 79 false alarms and 5 missed delays · rows: actual, columns: predicted",
        ),
        (
            "04-evaluation-metrics.png",
            metrics,
            "Validation and untouched final test",
            "Synthetic seed 42 · threshold selected on validation F1 · scores are not calibrated probabilities",
        ),
        (
            "05-feature-associations.png",
            importance,
            "Feature associations · permutation on validation",
            "Synthetic seed 42 · mean ± standard deviation of 3 repeats · association is not causation",
        ),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--snapshot", action="store_true", help="Rebuild plots from the saved public snapshot"
    )
    parser.add_argument("--browser-channel", default="chrome" if os.name == "nt" else None)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "synthetic-evaluation.json"
    data = json.loads(path.read_text(encoding="utf-8")) if args.snapshot else snapshot(args.api_url)
    if not args.snapshot:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scratch = ROOT / "artifacts" / "report-plots"
    scratch.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        launch = {"headless": True}
        if args.browser_channel:
            launch["channel"] = args.browser_channel
        browser = playwright.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": 1240, "height": 780}, device_scale_factor=1.5)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        for filename, figure, title, note in figures(data):
            margin = {"l": 110, "r": 80, "t": 120, "b": 140}
            margin.update(figure.layout.margin.to_plotly_json())
            figure.update_layout(
                template="plotly_white",
                width=1200,
                height=720,
                font={"family": "Arial", "size": 18, "color": INK},
                title={"text": title, "font": {"size": 25}, "x": 0.05},
                paper_bgcolor="white",
                plot_bgcolor="white",
                legend={"orientation": "h", "y": 1.08},
                margin=margin,
            )
            figure.add_annotation(
                x=0,
                y=-0.23,
                xref="paper",
                yref="paper",
                xanchor="left",
                text=note,
                showarrow=False,
                font={"size": 14, "color": "#526675"},
            )
            html = scratch / (filename + ".html")
            figure.write_html(
                html,
                include_plotlyjs=True,
                config={"displayModeBar": False, "staticPlot": True},
                post_script="window.__plotReady = true",
            )
            page.goto(html.as_uri())
            page.wait_for_function("window.__plotReady === true")
            page.locator(".js-plotly-plot").screenshot(path=str(OUTPUT / filename))
        if args.snapshot:
            assert not errors, errors
            browser.close()
            print("Rebuilt five figures from the saved synthetic evaluation snapshot")
            return
        page.goto("http://127.0.0.1:8501")
        expect(page.get_by_role("button", name="Charger la démonstration")).to_be_visible(
            timeout=60000
        )
        page.get_by_test_id("stSidebar").get_by_text("Commandes à surveiller", exact=True).click()
        expect(
            page.get_by_role("heading", name="Commandes à surveiller", exact=True)
        ).to_be_visible()
        page.get_by_test_id("stFileUploader").locator('input[type="file"]').set_input_files(
            str(ROOT / "examples" / "new_orders.csv")
        )
        page.get_by_role("button", name="Calculer les risques", exact=True).click()
        expect(page.get_by_role("button", name="Exporter le classement")).to_be_visible(
            timeout=30000
        )
        expect(page.get_by_test_id("stApp")).to_have_attribute(
            "data-test-script-state", "notRunning"
        )
        page.get_by_role("heading", name="Classement ML au moment de la commande").evaluate(
            "e => e.scrollIntoView({block:'start'})"
        )
        page.screenshot(path=str(ROOT / "docs" / "screenshots" / "07-risk-ranking.png"))
        page.get_by_test_id("stSidebar").get_by_text("Modèles et évaluation", exact=True).click()
        expect(page.get_by_role("checkbox", name="J'ai examiné", exact=False)).to_be_visible(
            timeout=30000
        )
        expect(page.get_by_test_id("stApp")).to_have_attribute(
            "data-test-script-state", "notRunning"
        )
        page.get_by_role("button", name="Activer cette version", exact=True).evaluate(
            "e => e.scrollIntoView({block:'end'})"
        )
        page.screenshot(path=str(ROOT / "docs" / "screenshots" / "08-model-limits.png"))
        assert not errors, errors
        browser.close()
    print(
        json.dumps(
            {
                "synthetic_source_verified": True,
                "run_id": data["run_id"],
                "figures": 5,
                "additional_ui_screenshots": 2,
                "page_errors": errors,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

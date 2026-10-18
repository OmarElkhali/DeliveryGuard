"""Real local UI E2E; requires a running synthetic demo and worker. No external service."""

import base64
import io
import json
import os
import time
from itertools import pairwise
from pathlib import Path

import requests
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get("DG_API_URL", "http://127.0.0.1:8000")
UI = os.environ.get("DG_UI_URL", "http://127.0.0.1:8501")


def main():
    assert requests.get(API + "/health/live", timeout=10).json()["demo"], "Synthetic demo only"
    artifacts = ROOT / "artifacts"
    shots = ROOT / "docs" / "screenshots"
    artifacts.mkdir(exist_ok=True)
    shots.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as playwright:
        launch = {"headless": True}
        if os.environ.get("PW_CHANNEL"):
            launch["channel"] = os.environ["PW_CHANNEL"]
        browser = playwright.chromium.launch(**launch)
        context_options = {"viewport": {"width": 1440, "height": 1000}}
        recording = os.environ.get("PW_NO_VIDEO") != "1"
        if recording:
            context_options.update(
                record_video_dir=str(artifacts / "video"),
                record_video_size={"width": 1280, "height": 900},
            )
        context = browser.new_context(**context_options)
        page = context.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        frames = []
        screencast = None
        if not recording:
            # Offline fallback: actual Chromium screen frames, encoded as GIF with Pillow.
            screencast = context.new_cdp_session(page)

            def frame_received(event):
                stamp = event["metadata"]["timestamp"]
                if not frames or stamp - frames[-1][0] >= 0.35:
                    frames.append((stamp, event["data"]))
                screencast.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

            screencast.on("Page.screencastFrame", frame_received)
            screencast.send(
                "Page.startScreencast",
                {
                    "format": "jpeg",
                    "quality": 70,
                    "maxWidth": 1280,
                    "maxHeight": 900,
                    "everyNthFrame": 2,
                },
            )

        def idle():
            expect(page.get_by_test_id("stApp")).to_have_attribute(
                "data-test-script-state", "notRunning", timeout=60000
            )

        def section(name):
            page.get_by_test_id("stSidebar").get_by_text(name, exact=True).click()
            expect(page.get_by_role("radio", name=name, exact=True)).to_be_checked()
            heading = "Qualité des données" if name == "Qualité" else name
            expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()
            idle()
            expect(page.get_by_test_id("stException")).to_have_count(0)

        def capture(name):
            idle()
            page.get_by_test_id("stMain").evaluate("e => e.scrollTo(0, 0)")
            page.screenshot(path=str(shots / name), full_page=True)

        page.goto(UI)
        expect(page.get_by_role("button", name="Charger la démonstration")).to_be_visible(
            timeout=60000
        )
        idle()
        capture("01-demo.png")
        section("Import et mapping")
        page.get_by_test_id("stFileUploader").locator('input[type="file"]').set_input_files(
            str(ROOT / "examples" / "synthetic.csv")
        )
        page.get_by_role("button", name="Prévisualiser et auditer").click()
        expect(page.get_by_role("button", name="Valider l'import", exact=True)).to_be_enabled(
            timeout=60000
        )
        idle()
        capture("02-import.png")
        page.get_by_role("button", name="Valider l'import", exact=True).click()
        expect(page.get_by_text("Import enregistré", exact=False)).to_be_visible(timeout=60000)
        idle()
        section("Qualité")
        expect(page.get_by_text("Aucune incohérence", exact=False)).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role(
                "button", name="Télécharger les lignes rejetées et leurs motifs"
            ).click()
        download.value.save_as(str(artifacts / "rejected.csv"))
        capture("03-quality.png")
        section("Analyse des livraisons")
        expect(page.get_by_test_id("stPlotlyChart")).to_have_count(2, timeout=30000)
        with page.expect_download() as download:
            page.get_by_role("button", name="Exporter les commandes pour Power BI").click()
        download.value.save_as(str(artifacts / "orders.csv"))
        capture("04-analytics.png")
        section("Modèles et évaluation")
        page.get_by_role("button", name="Créer un entraînement").click()
        expect(page.get_by_text("Entraînement en attente", exact=False)).to_be_visible(
            timeout=30000
        )
        idle()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            page.get_by_role("button", name="Actualiser les entraînements").click()
            page.wait_for_timeout(1000)
            idle()
            if page.get_by_role("checkbox", name="J'ai examiné", exact=False).count():
                break
            assert not page.get_by_test_id("stException").count()
        checkbox = page.get_by_role("checkbox", name="J'ai examiné", exact=False)
        expect(checkbox).to_be_visible(timeout=10000)
        capture("05-model.png")
        page.get_by_text(
            "J'ai examiné les métriques, les périodes et les limites", exact=True
        ).click()
        expect(checkbox).to_be_checked()
        page.get_by_role("button", name="Activer cette version", exact=True).click()
        expect(page.get_by_text("Version activée explicitement", exact=True)).to_be_visible()
        section("Commandes à surveiller")
        page.get_by_test_id("stFileUploader").locator('input[type="file"]').set_input_files(
            str(ROOT / "examples" / "new_orders.csv")
        )
        page.get_by_role("button", name="Calculer les risques", exact=True).click()
        expect(page.get_by_role("button", name="Exporter le classement")).to_be_visible(
            timeout=30000
        )
        capture("06-predictions.png")
        with page.expect_download() as download:
            page.get_by_role("button", name="Exporter le classement").click()
        download.value.save_as(str(artifacts / "risk_scores.csv"))
        assert "risk_score" in (artifacts / "risk_scores.csv").read_text(encoding="utf-8-sig")
        assert not errors, errors
        expect(page.get_by_test_id("stException")).to_have_count(0)
        if screencast:
            from PIL import Image

            screencast.send("Page.stopScreencast")
            images = [
                Image.open(io.BytesIO(base64.b64decode(raw))).convert("RGB") for _, raw in frames
            ]
            durations = [
                max(100, min(2000, int((b[0] - a[0]) * 1000))) for a, b in pairwise(frames)
            ] + [1500]
            images[0].save(
                artifacts / "demo.gif",
                save_all=True,
                append_images=images[1:],
                duration=durations,
                loop=0,
                optimize=True,
            )
        context.close()
        browser.close()
    result = {
        "status": "passed",
        "console_errors": errors,
        "video_recorded": recording,
        "gif_screencast": not recording,
        "flow": [
            "CSV upload",
            "mapping",
            "preview",
            "import",
            "quality",
            "rejected download",
            "analytics",
            "CSV export",
            "training",
            "explicit activation",
            "batch prediction",
            "risk export",
        ],
    }
    (artifacts / "browser-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

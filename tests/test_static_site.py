from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_static_site_has_required_pages_and_local_assets() -> None:
    index = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    app_script = (ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
    docs_script = (ROOT / "site" / "assets" / "docs.js").read_text(encoding="utf-8")
    assert 'id="phan-tich"' in index
    assert 'id="du-doan"' in index
    assert "assets/app.js" in index
    assert "https://cdn." not in index
    assert '{ cache: "no-store" }' in app_script
    assert '{ cache: "no-store" }' in docs_script
    assert (ROOT / "site" / "phuong-phap.html").exists()
    assert (ROOT / "site" / "du-lieu.html").exists()
    assert (ROOT / "site" / ".nojekyll").exists()


def test_generated_site_data_matches_manifest() -> None:
    data_root = ROOT / "site" / "data"
    manifest = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    predictions = json.loads((data_root / "predictions.json").read_text(encoding="utf-8"))

    assert manifest["draw_rows"] >= manifest["confirmed_rows"]
    assert predictions["model_version"]
    for product in manifest["products"]:
        report = json.loads(
            (data_root / "products" / f"{product['slug']}.json").read_text(encoding="utf-8")
        )
        assert report["product"]["slug"] == product["slug"]
        assert report["summary"]["confirmed_draws"] == product["confirmed_draws"]

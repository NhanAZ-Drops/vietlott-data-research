from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_static_site_has_required_pages_and_local_assets() -> None:
    index = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    method_page = (ROOT / "site" / "phuong-phap.html").read_text(encoding="utf-8")
    data_page = (ROOT / "site" / "du-lieu.html").read_text(encoding="utf-8")
    styles = (ROOT / "site" / "assets" / "styles.css").read_text(encoding="utf-8")
    app_script = (ROOT / "site" / "assets" / "app.js").read_text(encoding="utf-8")
    docs_script = (ROOT / "site" / "assets" / "docs.js").read_text(encoding="utf-8")
    assert 'id="phan-tich"' in index
    assert 'id="du-doan"' in index
    assert "assets/styles.css?v=20260614-3" in index
    assert "assets/app.js?v=20260614-2" in index
    assert "assets/docs.js?v=20260614-1" in data_page
    for page in (index, method_page, data_page):
        assert "cdn-uicons.flaticon.com/3.0.0" in page
        assert "fi-rr-crystal-ball" in page
        assert "Biểu tượng từ UIcons by Flaticon" in page
    assert "[hidden]" in styles
    assert "display: none !important" in styles
    assert "min-height: 72px" in styles
    assert "Chọn ngẫu nhiên có thể lặp lại" in app_script
    assert "Kết luận: cách kết hợp dấu hiệu chưa tốt hơn chọn ngẫu nhiên." in app_script
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

from __future__ import annotations

import json
import unicodedata
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
    assert 'id="kiem-dinh"' in index
    assert "assets/app.js?v=20260614-6" in index
    assert "assets/docs.js?v=20260614-2" in data_page
    for page in (index, method_page, data_page):
        assert "assets/styles.css?v=20260614-6" in page
        assert "fonts.googleapis.com/css2?family=Noto+Serif" in page
        assert "cdn-uicons.flaticon.com/3.0.0" in page
        assert "fi-rr-crystal-ball" in page
        assert "Biểu tượng từ UIcons by Flaticon" in page
    assert "[hidden]" in styles
    assert "display: none !important" in styles
    assert "min-height: 72px" in styles
    assert '--font-display: "Noto Serif"' in styles
    assert "Georgia" not in styles
    assert "Cambria" not in styles
    assert '.normalize("NFC")' in app_script
    assert '.normalize("NFC")' in docs_script
    assert "Chọn ngẫu nhiên có thể lặp lại" in app_script
    assert "Kết luận: cách kết hợp dấu hiệu chưa tốt hơn chọn ngẫu nhiên." in app_script
    assert "renderFairnessAudit" in app_script
    assert "audit-log.jsonl" in index
    assert "audit-summary.json" in data_page
    assert '{ cache: "no-store" }' in app_script
    assert '{ cache: "no-store" }' in docs_script
    assert (ROOT / "site" / "phuong-phap.html").exists()
    assert (ROOT / "site" / "du-lieu.html").exists()
    assert (ROOT / "site" / ".nojekyll").exists()


def test_static_site_text_is_normalized_unicode() -> None:
    text_suffixes = {".css", ".html", ".js", ".json"}
    for path in (ROOT / "site").rglob("*"):
        if path.is_file() and path.suffix.lower() in text_suffixes:
            content = path.read_text(encoding="utf-8")
            assert unicodedata.is_normalized("NFC", content), path


def test_generated_site_data_matches_manifest() -> None:
    data_root = ROOT / "site" / "data"
    manifest = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    predictions = json.loads((data_root / "predictions.json").read_text(encoding="utf-8"))
    audit_summary = json.loads((data_root / "audit-summary.json").read_text(encoding="utf-8"))
    audit_log = (data_root / "audit-log.jsonl").read_text(encoding="utf-8")

    assert manifest["draw_rows"] >= manifest["confirmed_rows"]
    assert predictions["model_version"]
    assert manifest["fairness_audit"]["test_count"] == audit_summary["summary"]["test_count"]
    assert audit_summary["suite_version"] == "1.0.0"
    assert audit_log
    for product in manifest["products"]:
        report = json.loads(
            (data_root / "products" / f"{product['slug']}.json").read_text(encoding="utf-8")
        )
        assert report["product"]["slug"] == product["slug"]
        assert report["summary"]["confirmed_draws"] == product["confirmed_draws"]
        assert report["audit"]["suite_version"] == "1.0.0"

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_research_documentation_and_issue_templates_exist() -> None:
    required = [
        ROOT / "docs" / "DATA_DICTIONARY.md",
        ROOT / "docs" / "AUDIT_EFFECT_THRESHOLDS.md",
        ROOT / "docs" / "AUDIT_TEST_DEPENDENCIES.md",
        ROOT / "docs" / "AUDIT_TIER_BREAKDOWN.md",
        ROOT / "docs" / "METHODOLOGY_CHANGELOG.md",
        ROOT / "docs" / "templates" / "BAO_CAO_KET_QUA_AM.md",
        ROOT / "docs" / "DU_DOAN_BINGO18_0171884.md",
        ROOT / "docs" / "protocols" / "MAX3D_POSITION_CONFIRMATION.md",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "loi-du-lieu.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "loi-nguon.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "tin-hieu-thong-ke.yml",
    ]

    for path in required:
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").strip(), path


def test_readme_links_research_documents_without_em_dash() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/DATA_DICTIONARY.md" in readme
    assert "docs/AUDIT_EFFECT_THRESHOLDS.md" in readme
    assert "docs/AUDIT_TEST_DEPENDENCIES.md" in readme
    assert "docs/AUDIT_TIER_BREAKDOWN.md" in readme
    assert "docs/METHODOLOGY_CHANGELOG.md" in readme
    assert "docs/templates/BAO_CAO_KET_QUA_AM.md" in readme
    assert "docs/DU_DOAN_BINGO18_0171884.md" in readme
    assert "docs/protocols/MAX3D_POSITION_CONFIRMATION.md" in readme
    assert "—" not in readme


def test_statistical_signal_issue_template_has_interpretation_guardrails() -> None:
    template = (
        ROOT / ".github" / "ISSUE_TEMPLATE" / "tin-hieu-thong-ke.yml"
    ).read_text(encoding="utf-8")

    assert "không kết luận gian lận" in template
    assert "Kết quả âm" in template
    assert "q, độ lớn hiệu ứng" in template


def test_effect_threshold_documentation_has_required_review_fields() -> None:
    document = (ROOT / "docs" / "AUDIT_EFFECT_THRESHOLDS.md").read_text(encoding="utf-8")

    assert "Đơn vị" in document
    assert "Phạm vi áp dụng" in document
    assert "Lập luận hoặc tham khảo" in document
    assert "Phân tích độ nhạy" in document
    assert "threshold_sensitivity" in document


def test_audit_dependency_documentation_has_required_fields() -> None:
    document = (ROOT / "docs" / "AUDIT_TEST_DEPENDENCIES.md").read_text(encoding="utf-8")

    assert "dependency_matrix" in document
    assert "q_value_dependency_family_bh" in document
    assert "q_value_global_bh" in document
    assert "high" in document
    assert "medium" in document
    assert "low" in document


def test_audit_tier_breakdown_documentation_has_required_fields() -> None:
    document = (ROOT / "docs" / "AUDIT_TIER_BREAKDOWN.md").read_text(encoding="utf-8")

    assert "tier_breakdown" in document
    assert "digit_position_chi_square" in document
    assert "full_sequence" in document
    assert "wildcard_prefix" in document
    assert "không phải một bộ kiểm định mới" in document

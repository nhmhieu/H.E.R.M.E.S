"""
Unit tests for H.E.R.M.E.S Regulation Retriever (Role R3).
"""

from hermes.rag.retriever import (
    ALIAS_CHUONG_TRINH,
    ALIAS_NGANH,
    KeywordRetriever,
    bo_dau,
    nhan_dien,
    nhan_dien_khoa,
)


def test_bo_dau_normalizes_vietnamese():
    assert bo_dau("Chuẩn đầu ra Tiếng Anh ĐH KHTN") == "chuan dau ra tieng anh dh khtn"


def test_nhan_dien_khoa_extracts_cohort_year():
    year, rest = nhan_dien_khoa("sinh vien khoa 2024 nganh cntt")
    assert year == 2024
    assert "2024" not in rest

    year_short, _ = nhan_dien_khoa("em hoc k25 chuong trinh dai tra")
    assert year_short == 2025


def test_nhan_dien_nganh_and_chuong_trinh():
    nganh, _ = nhan_dien("nganh cong nghe thong tin", ALIAS_NGANH)
    assert "Công nghệ thông tin" in nganh

    ct, _ = nhan_dien("chuong trinh tien tien khmt", ALIAS_CHUONG_TRINH)
    assert "tiên tiến" in ct


def test_retriever_search_foreign_language_advanced_cs():
    retriever = KeywordRetriever()
    res = retriever.search(
        "Chuẩn đầu ra tiếng Anh chương trình tiên tiến ngành Khoa học máy tính cần IELTS bao nhiêu?"
    )
    assert "tiên tiến" in res["chuong_trinh"]
    assert len(res["ket_qua"]) > 0
    top = res["ket_qua"][0]
    assert "1985" in top["trich_dan"] or "2467" in top["trich_dan"]


def test_retriever_search_foreign_language_tcta_cntt():
    retriever = KeywordRetriever()
    res = retriever.search(
        "Chuẩn đầu ra ngoại ngữ chương trình tăng cường tiếng Anh ngành Công nghệ thông tin khóa 2024"
    )
    assert "Công nghệ thông tin" in res["nganh"]
    assert "tăng cường tiếng Anh" in res["chuong_trinh"]
    assert res["khoa_tuyen"] == 2024
    assert len(res["ket_qua"]) > 0
    assert any("1984" in item["trich_dan"] for item in res["ket_qua"])


def test_retriever_search_foreign_language_dai_tra():
    retriever = KeywordRetriever()
    res = retriever.search(
        "Quy định chuẩn đầu ra ngoại ngữ chương trình đại trà khóa 2025"
    )
    assert "đại trà" in res["chuong_trinh"]
    assert len(res["ket_qua"]) > 0
    assert any("2464" in item["trich_dan"] for item in res["ket_qua"])


def test_retriever_search_academic_warning():
    retriever = KeywordRetriever()
    res = retriever.search("Quy chế cảnh báo học vụ và buộc thôi học")
    assert len(res["ket_qua"]) > 0
    assert any("Điều" in item["trich_dan"] for item in res["ket_qua"])


def test_retriever_out_of_scope_query_returns_empty():
    retriever = KeywordRetriever()
    res = retriever.search("pizza sushi pasta burger ramen taco")
    assert res["ket_qua"] == []

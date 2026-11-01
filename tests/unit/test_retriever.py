import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from hermes.rag.retriever import KeywordRetriever, bo_dau


def _vb(vid, nganh=None, het_hieu_luc=None):
    return {
        "van_ban_id": vid,
        "ten_van_ban": f"Văn bản {vid}",
        "loai": "Quy định",
        "so_hieu": f"{vid}/QĐ",
        "chuong_trinh": "",
        "nganh": nganh or [],
        "file_nguon": f"{vid}.pdf",
        "het_hieu_luc": het_hieu_luc,
    }


def _chunk(cid, text, vid="vb1", ten_dieu="Điều khoản chung", chu_de="chung"):
    return {
        "chunk_id": cid,
        "van_ban_id": vid,
        "dieu": "1",
        "khoan": None,
        "ten_dieu": ten_dieu,
        "chu_de": chu_de,
        "trang_start": 1,
        "trang_end": 1,
        "text": text,
    }


def build(tmp_path, chunks, van_ban=None):
    """Ghi json giả và và trả về retriever."""
    data = {"van_ban": van_ban or [_vb("vb1")], "chunks": chunks}
    p = tmp_path / "data.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return KeywordRetriever(p)


def ids(result):
    return [k["chunk_id"] for k in result["ket_qua"]]


# ---------- 1-3: IDF ----------
def test_idf_tu_hiem_lon_hon_tu_pho_bien(tmp_path):
    r = build(
        tmp_path,
        [
            _chunk("a", "sinh vien hoc ielts"),
            _chunk("b", "sinh vien hoc toeic"),
            _chunk("c", "sinh vien hoc jlpt"),
        ],
    )
    assert r.idf["ielts"] > r.idf["sinh"]  # 'ielts' chỉ ở 1 chunk, 'sinh' ở cả 3


def test_idf_dung_cong_thuc(tmp_path):
    r = build(
        tmp_path,
        [_chunk("a", "alpha beta"), _chunk("b", "alpha gamma"), _chunk("c", "delta")],
    )
    n, k = 3, 2  # 'alpha' xuất hiện ở 2 trong 3 chunk
    assert r.idf["alpha"] == pytest.approx(math.log(1 + (n - k + 0.5) / (k + 0.5)))


def test_idf_khong_am_ke_ca_khi_tu_co_o_moi_chunk(tmp_path):
    r = build(tmp_path, [_chunk("a", "chung rieng1"), _chunk("b", "chung rieng2")])
    assert r.idf["chung"] > 0  # BM25 dạng log(1+x) không bao giờ âm


# ---------- 4-5: TF ----------
def test_tf_cang_nhieu_diem_cang_cao(tmp_path):
    r = build(
        tmp_path,
        [
            _chunk("it", "ielts"),
            _chunk("nhieu", "ielts ielts ielts ielts"),
            _chunk("khac", "toeic xyz"),  # để 'ielts' có IDF > 0
        ],
    )
    diem = {
        k["chunk_id"]: k["diem"]
        for k in r.search("ielts", top_k=5, min_score=0, min_ratio=0)["ket_qua"]
    }
    assert diem["nhieu"] > diem["it"]


def test_tf_bao_hoa_khong_tang_tuyen_tinh(tmp_path):
    r = build(
        tmp_path,
        [
            _chunk("it", "ielts"),
            _chunk("nhieu", "ielts ielts ielts ielts"),
            _chunk("khac", "toeic xyz"),
        ],
    )
    diem = {
        k["chunk_id"]: k["diem"]
        for k in r.search("ielts", top_k=5, min_score=0, min_ratio=0)["ket_qua"]
    }
    assert diem["nhieu"] < 4 * diem["it"]  # lặp 4 lần không được gấp 4 điểm


# ---------- 6: từ hiếm áp đảo từ phổ biến ----------
def test_tu_hiem_ap_dao_tu_pho_bien(tmp_path):
    r = build(
        tmp_path,
        [
            _chunk("co_hiem", "sinh vien ielts"),
            _chunk("co_pho_bien", "sinh vien sinh vien sinh vien hoc"),
            _chunk("n1", "sinh vien hoc"),
            _chunk("n2", "sinh vien hoc"),
            _chunk("n3", "sinh vien hoc"),
        ],
    )
    assert ids(r.search("sinh vien ielts"))[0] == "co_hiem"


# ---------- 7: thưởng tiêu đề ----------
def test_tu_trong_tieu_de_duoc_cong_diem(tmp_path):
    r = build(
        tmp_path,
        [
            _chunk("tieu_de", "noi dung khac", ten_dieu="Chuẩn IELTS"),
            _chunk("noi_dung", "chuan ielts o day", ten_dieu="Điều khoản chung"),
            _chunk("n", "khong lien quan"),
        ],
    )
    diem = {
        k["chunk_id"]: k["diem"]
        for k in r.search("ielts", top_k=5, min_score=0, min_ratio=0)["ket_qua"]
    }
    assert diem["tieu_de"] > diem["noi_dung"]


# ---------- 8: bỏ dấu / hoa thường ----------
def test_khong_phan_biet_dau_va_hoa_thuong(tmp_path):
    r = build(
        tmp_path,
        [_chunk("a", "Chứng chỉ IELTS tối thiểu"), _chunk("b", "nội dung khác")],
    )
    assert bo_dau("Chứng chỉ Đạt") == "chung chi dat"
    assert ids(r.search("CHUNG CHI ielts"))[0] == "a"
    assert ids(r.search("chứng chỉ IELTS"))[0] == "a"


# ---------- 9: sắp xếp, top_k, câu ngoài phạm vi ----------
def test_ket_qua_giam_dan_va_ton_trong_top_k(tmp_path):
    r = build(
        tmp_path,
        [_chunk(f"c{i}", "ielts " * (i + 1) + "x") for i in range(5)]
        + [_chunk("z", "khac")],
    )
    out = r.search("ielts", top_k=3, min_score=0, min_ratio=0)["ket_qua"]
    diem = [k["diem"] for k in out]
    assert len(out) == 3
    assert diem == sorted(diem, reverse=True)


def test_cau_ngoai_pham_vi_tra_ve_rong(tmp_path):
    r = build(
        tmp_path, [_chunk("a", "chuan ielts dau ra"), _chunk("b", "toeic dau ra")]
    )
    assert r.search("thoi tiet sai gon hom nay")["ket_qua"] == []


# ---------- 10: lọc metadata ----------
def test_van_ban_het_hieu_luc_bi_loai(tmp_path):
    r = build(
        tmp_path,
        [
            _chunk("moi", "chuan ielts", vid="moi"),
            _chunk("cu", "chuan ielts", vid="cu"),
            _chunk("n", "khac", vid="moi"),
        ],
        van_ban=[_vb("moi"), _vb("cu", het_hieu_luc="2025-01-01")],
    )
    assert "cu" not in ids(r.search("ielts", top_k=5, min_score=0, min_ratio=0))


def test_thong_bao_khi_khong_tim_thay(tmp_path):
    r = build(
        tmp_path, [_chunk("a", "chuan ielts dau ra"), _chunk("b", "toeic dau ra")]
    )
    out = r.search("thoi tiet sai gon hom nay")
    assert out["thong_bao"] == "Không tìm thấy quy định phù hợp"
    assert r.search("ielts", min_score=0, min_ratio=0)["thong_bao"] is None

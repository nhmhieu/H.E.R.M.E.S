from __future__ import annotations

import argparse  # đọc tham số dòng lệnh
import json
import math
import re  # regex tìm alies và tách từ
import unicodedata  # xử lý dấu tiếng việt
from collections import Counter
from pathlib import Path

_ME = Path(__file__).resolve()
_ROOT = _ME.parents[3] if len(_ME.parents) > 3 else _ME.parent
# file nằm quá nông không đủ 3 cấp thì lấy thư mục chứa file
DEFAULT_DATA = _ROOT / "data" / "processed" / "hcmus_regulations.json"

ALIAS_NGANH = {
    "cong nghe ky thuat hoa hoc": "Công nghệ kỹ thuật hóa học",
    "hoa hoc": "Hóa học",
    "sinh hoc": "Sinh học",
    "cong nghe sinh hoc": "Công nghệ sinh học",
    "cnsh": "Công nghệ sinh học",
    "ky thuat dien tu vien thong": "Kỹ thuật điện tử - viễn thông",
    "dien tu vien thong": "Kỹ thuật điện tử - viễn thông",
    "dtvt": "Kỹ thuật điện tử - viễn thông",
    "khoa hoc moi truong": "Khoa học môi trường",
    "moi truong": "Khoa học môi trường",
    "vat ly hoc": "Vật lý học",
    "vat ly": "Vật lý học",
    "khoa hoc vat lieu": "Khoa học vật liệu",
    "vat lieu": "Khoa học vật liệu",
    "cong nghe thong tin": "Công nghệ thông tin",
    "cntt": "Công nghệ thông tin",
    "khoa hoc may tinh": "Khoa học máy tính",
    "khmt": "Khoa học máy tính",
    "may tinh": "Khoa học máy tính",
}

ALIAS_CHUONG_TRINH = {
    "tang cuong tieng anh": "tăng cường tiếng Anh",
    "tang cuong": "tăng cường tiếng Anh",
    "chat luong cao": "tăng cường tiếng Anh",
    "clc": "tăng cường tiếng Anh",
    "tien tien": "tiên tiến",
    "cttt": "tiên tiến",
    "dai tra": "đại trà",
    "chuong trinh chuan": "đại trà",
    "cu nhan tai nang": "cử nhân tài năng",
    "tai nang": "cử nhân tài năng",
    "cntn": "cử nhân tài năng",
    
}

STOPWORDS = {
    "la",
    "cua",
    "va",
    "hoac",
    "co",
    "khong",
    "bao",
    "nhieu",
    "can",
    "phai",
    "de",
    "thi",
    "cho",
    "em",
    "minh",
    "toi",
    "ban",
    "nao",
    "gi",
    "the",
    "nhu",
    "duoc",
    "o",
    "trong",
    "khi",
    "nay",
    "do",
    "hoc",
    "nganh",
    "a",
    "b",
    "c",
    "sao",
}

# Sinh viên hỏi bằng ngôn ngữ đời thường, văn bản dùng thuật ngữ chính thức.
# Khóa = cụm từ (đã bỏ dấu) trong câu hỏi; giá trị = các từ được THÊM vào truy vấn (không thay thế).
MO_RONG = {
    "rot mon": "khong dat hoc lai",
    "rot": "khong dat hoc lai",
    "truot": "khong dat hoc lai",
    "bi f": "khong dat hoc lai thang diem diem chu",
    "diem f": "khong dat hoc lai thang diem diem chu",
    "thi lai": "hoc lai hoan thi",
    "dtb": "diem trung binh",
    "diem tb": "diem trung binh",
    "gpa": "diem trung binh tich luy",
    "cpa": "diem trung binh tich luy",
    "hoc luc": "xep loai diem trung binh",
    "xep loai": "diem trung binh xuat sac gioi kha",
    "xep hang": "diem trung binh tich luy xuat sac gioi",
    "duoi hoc": "buoc thoi hoc",
    "bi duoi": "buoc thoi hoc",
    "bo hoc": "buoc thoi hoc tu y bo hoc",
    "ra truong": "tot nghiep",
    "bang cap": "bang tot nghiep",
    "bao luu": "nghi hoc tam thoi bao luu ket qua",
    "tam nghi": "nghi hoc tam thoi",
    "mien mon": "mien hoc cong nhan chuyen doi tin chi",
    "mien hoc": "cong nhan ket qua chuyen doi tin chi",
    "song nganh": "hoc cung luc hai chuong trinh",
    "hai nganh": "hoc cung luc hai chuong trinh",
    "bang hai": "hoc cung luc hai chuong trinh",
    "bang 2": "hoc cung luc hai chuong trinh",
    "chuyen nganh": "chuyen chuong trinh",
    "online": "truc tuyen",
    "dkhp": "dang ky hoc phan",
    "dang ky mon": "dang ky hoc phan",
    "mon hoc": "hoc phan",
    "hoc vuot": "dang ky vuot so tin chi toi da",
    "thi ho": "thi ho dinh chi hoc tap ky luat",
    "gian lan": "gian lan thi ky luat",
    "do an": "do an tot nghiep khoa luan",
    "khoa luan": "khoa luan tot nghiep do an",
    "hoc toi da": "thoi gian toi da hoan thanh khoa hoc",
}


def mo_rong(q: str) -> list[str]:
    them = []
    for k in sorted(MO_RONG, key=len, reverse=True):
        if re.search(rf"\b{k}\b", q):
            them += MO_RONG[k].split()
    return them


def bo_dau(s: str) -> str:
    s = unicodedata.normalize(
        "NFD", s.lower()
    )  # tách ký tự có dấu thanh chữ gốc và dấu
    s = "".join(
        ch for ch in s if unicodedata.category(ch) != "Mn"
    )  # duyệt các kí tự trừ dấu
    return s.replace("đ", "d")


def tach_tu(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", bo_dau(s))


def nhan_dien(q: str, bang_alias: dict[str, str]) -> tuple[set[str], str]:
    tim_thay: set[str] = set()
    for alias in sorted(bang_alias, key=len, reverse=True):
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, q):
            tim_thay.add(bang_alias[alias])
            q = re.sub(pattern, " ", q)
    return tim_thay, q


# "khoa tuyen 2023", "khoa 2023", "k2023", "k23" (23 -> 2023)
_RE_KHOA = re.compile(r"\b(?:khoa tuyen|khoa|k)\s*(20\d{2}|[12]\d)\b")


def nhan_dien_khoa(q: str) -> tuple[int | None, str]:
    m = _RE_KHOA.search(q)
    if not m:
        return None, q
    n = int(m.group(1))
    return (n if n >= 2000 else 2000 + n), _RE_KHOA.sub(" ", q)


def _thua_huong(chunk: dict, vb: dict, key: str):
    """Chunk ghi đè giá trị của văn bản nếu có khóa đó (kể cả giá trị null)."""
    return chunk[key] if key in chunk else vb.get(key)


def _quy_tac(chunk: dict, vb: dict) -> list[tuple[set[str], int | None, int | None]]:
    """Danh sách (tập chương trình, khóa từ, khóa đến) mà chunk áp dụng.

    Tập chương trình rỗng = áp dụng mọi chương trình. Ưu tiên 'pham_vi' của chunk.
    """
    mac_tu, mac_den = vb.get("khoa_tuyen_tu"), vb.get("khoa_tuyen_den")
    if chunk.get("pham_vi"):
        return [
            (set(r["chuong_trinh"]), r.get("khoa_tuyen_tu", mac_tu), r.get("khoa_tuyen_den", mac_den))
            for r in chunk["pham_vi"]
        ]
    ct = _thua_huong(chunk, vb, "chuong_trinh_ap_dung") or [vb.get("chuong_trinh", "")]
    return [({x for x in ct if x}, _thua_huong(chunk, vb, "khoa_tuyen_tu"), _thua_huong(chunk, vb, "khoa_tuyen_den"))]


def _nhan_khoa(quy_tac) -> str:
    cac = []
    for ct, tu, den in quy_tac:
        kh = " ".join(x for x in (f"từ {tu}" if tu else "", f"đến {den}" if den else "") if x)
        cac.append(f"{'/'.join(sorted(ct)) or 'mọi chương trình'}: {kh or 'mọi khóa'}")
    return "; ".join(cac)


def khop_pham_vi(d: dict, chuong_trinh: set[str], khoa: int | None) -> bool:
    """Chunk khớp nếu ÍT NHẤT MỘT quy tắc khớp đồng thời chương trình và khóa."""
    for ct, tu, den in d["quy_tac"]:
        if chuong_trinh and ct and not (ct & chuong_trinh):
            continue
        if khoa is not None and ((tu is not None and khoa < tu) or (den is not None and khoa > den)):
            continue
        return True
    return False


def trich_dan(chunk: dict, vb: dict) -> str:
    s = f"{vb['loai']} {vb['so_hieu']}".strip() if vb["so_hieu"] else vb["ten_van_ban"]
    if chunk.get("dieu"):
        s += f", Điều {chunk['dieu']}"
    if chunk.get("khoan"):
        s += f", Khoản {chunk['khoan']}"
    t1, t2 = chunk["trang_start"], chunk["trang_end"]
    s += f", trang {t1}" if t1 == t2 else f", trang {t1}-{t2}"
    return f"{s} ({vb['file_nguon']})"


class KeywordRetriever:

    def __init__(self, data_path: str | Path = DEFAULT_DATA):
        data = json.loads(Path(data_path).read_text(encoding="utf-8"))
        # khóa bắt đầu bằng '_' (ví dụ _huong_dan_them_du_lieu) bị bỏ qua
        van_ban = {v["van_ban_id"]: v for v in data["van_ban"]}

        self.docs = []
        for c in data["chunks"]:
            vb = van_ban[c["van_ban_id"]]
            if vb.get("het_hieu_luc"):
                continue
            quy_tac = _quy_tac(c, vb)
            ct_ap_dung = sorted(set().union(*[r[0] for r in quy_tac]))
            head = " ".join(
                [
                    c["ten_dieu"],
                    c["chu_de"],
                    vb["ten_van_ban"],
                    vb["chuong_trinh"],
                    " ".join(ct_ap_dung),
                    " ".join(vb.get("chuong_trinh_alias", [])),
                    " ".join((c.get("chung_chi_toi_thieu") or {}).keys()),  # IELTS, TOEIC... nằm trong tiêu đề chunk
                ]
            )
            self.docs.append(
                {
                    "chunk": c,
                    "vb": vb,
                    "quy_tac": quy_tac,
                    "tf": Counter(tach_tu(c["text"])),  # tần suất từ trong nội dung
                    "head": set(
                        tach_tu(head)
                    ),  # từ trong tiêu đề/chủ đề, được cộng thêm điểm
                    # chuỗi từ liền nhau (đã bỏ dấu) để kiểm tra cụm "buoc thoi hoc", "hoc lai"...
                    "norm": " "
                    + " ".join(tach_tu(f"{c['ten_dieu']} {c['chu_de']} {c['text']}"))
                    + " ",
                }
            )

        self._df_cum: dict[str, int] = {}  # cache số chunk chứa mỗi cụm 2 từ
        n = len(self.docs)
        df: Counter = Counter()
        for d in self.docs:
            df.update(set(d["tf"]) | d["head"])
        self.idf = {t: math.log(1 + (n - k + 0.5) / (k + 0.5)) for t, k in df.items()}

    def search(
        self,
        query: str,
        top_k: int = 3,
        min_score: float = 0.5,
        min_ratio: float = 0.25,
        min_coverage: float = 0.35,
    ) -> dict:
        q = bo_dau(query)
        # "khóa 2023" / "K2023" / "K23": lọc theo khóa tuyển, không đưa vào từ khóa tìm kiếm
        khoa, q = nhan_dien_khoa(q)
        nganh, q = nhan_dien(q, ALIAS_NGANH)
        chuong_trinh, q = nhan_dien(q, ALIAS_CHUONG_TRINH)
        day_tu = re.findall(r"[a-z0-9]+", q)
        w_tok = {t: 1.0 for t in day_tu if t not in STOPWORDS}
        for t in mo_rong(q):  # từ suy ra từ từ đồng nghĩa chỉ tính nửa trọng số
            if t not in STOPWORDS:
                w_tok.setdefault(t, 0.5)
        tokens = set(w_tok)
        # từ lạ (không có trong kho dữ liệu) = tín hiệu câu hỏi ngoài phạm vi
        max_w = max((v**2 for v in self.idf.values()), default=0.0)
        tong_w = sum(
            w_tok[t] * (self.idf[t] ** 2 if t in self.idf else max_w) for t in tokens
        )
        # cặp từ liền nhau trong câu hỏi (bỏ cặp gồm toàn từ dừng)
        cap_tu = [
            (a, b)
            for a, b in zip(day_tu, day_tu[1:])
            if not (a in STOPWORDS and b in STOPWORDS)
        ]

        # độ hiếm của từng cụm 2 từ (vd. "thi ho" chỉ có ở vài chunk -> thưởng lớn; "bi xu" phổ biến -> nhỏ)
        cum_hiem = []
        for a, b in cap_tu:
            cum = f" {a} {b} "
            if cum not in self._df_cum:
                self._df_cum[cum] = sum(1 for d in self.docs if cum in d["norm"])
            df_c = self._df_cum[cum]
            if df_c:
                cum_hiem.append(
                    (cum, math.log(1 + (len(self.docs) - df_c + 0.5) / (df_c + 0.5)))
                )

        # loc theo metadata
        ung_vien = [
            d
            for d in self.docs
            if (
                not nganh
                or not d["vb"]["nganh"]
                or any(n in d["vb"]["nganh"] for n in nganh)
            )
            and khop_pham_vi(d, chuong_trinh, None)  # lọc chương trình; khóa lọc ở bước sau
        ]
        # khóa tuyển: lọc nghiêm; nếu không còn kết quả thì nới lỏng khóa và cảnh báo
        ung_vien_khoa = [d for d in ung_vien if khop_pham_vi(d, chuong_trinh, khoa)] if khoa else ung_vien

        def cham_diem(ds_ung_vien):
            ket_qua = []
            for d in ds_ung_vien:
                diem = 0.0
                khop = 0.0
                for t in tokens:
                    if t not in self.idf:
                        continue
                    trong_so = (
                        w_tok[t] * self.idf[t] ** 2
                    )  # bình phương: từ hiếm (ielts, toeic...) áp đảo từ chung
                    tf = d["tf"].get(t, 0)
                    if tf or t in d["head"]:
                        khop += trong_so
                    if tf:
                        diem += trong_so * (1 + math.log(tf))
                    if t in d["head"]:
                        diem += trong_so * 1.5
                for (
                    cum,
                    idf_cum,
                ) in (
                    cum_hiem
                ):  # thưởng khi cả cụm xuất hiện liền nhau, theo độ hiếm của CỤM
                    if cum in d["norm"]:
                        diem += idf_cum**2
                # độ phủ: phần trọng số của câu hỏi mà chunk này khớp được (câu ngoài phạm vi thường < 0.35)
                if diem > 0 and (tong_w == 0 or khop / tong_w >= min_coverage):
                    ket_qua.append((diem, d))

            def loc(
                ds,
            ):  # sắp xếp + bỏ điểm quá thấp (tuyệt đối min_score, hoặc so với kết quả đầu min_ratio)
                ds = sorted(ds, key=lambda x: x[0], reverse=True)
                if not ds:
                    return ds
                nguong = max(min_score, min_ratio * ds[0][0])
                return [x for x in ds if x[0] >= nguong]

            if (
                nganh or chuong_trinh
            ):  # người dùng nêu ngành/chương trình: ưu tiên nhẹ văn bản riêng của ngành
                ket_qua = [
                    (diem * 1.5 if d["vb"]["nganh"] else diem, d) for diem, d in ket_qua
                ]
            return loc(ket_qua)

        ket_qua = cham_diem(ung_vien_khoa)
        ngoai_khoa = False
        if khoa and not ket_qua:
            ket_qua = cham_diem(ung_vien)
            ngoai_khoa = bool(ket_qua)

        # Hỏi lại khi các chunk liên quan nhất có MỨC ĐIỂM KHÁC NHAU giữa các nhóm chuẩn
        # (nhom_chuan) mà người dùng chưa nêu đủ để chọn một nhóm. Xét trên mọi chunk gần
        # điểm đầu (không chỉ top_k) và trả chunk tốt nhất của từng nhóm.
        gan_dau = [x for x in ket_qua if x[0] >= 0.6 * ket_qua[0][0]] if ket_qua else []
        nhom = {
            d["vb"].get("nhom_chuan")
            for _, d in gan_dau
            if d["chunk"].get("chung_chi_toi_thieu")
        } - {None}
        can_hoi_lai = len(nhom) > 1
        if can_hoi_lai:
            moi_nhom, da_co = [], set()
            for x in gan_dau:
                n = x[1]["vb"].get("nhom_chuan")
                if x[1]["chunk"].get("chung_chi_toi_thieu") and n not in da_co:
                    da_co.add(n)
                    moi_nhom.append(x)
            ket_qua = (moi_nhom + [x for x in ket_qua if x not in moi_nhom])[: max(top_k, len(moi_nhom))]
        else:
            ket_qua = ket_qua[:top_k]

        # Đáp án phụ thuộc khóa tuyển (chunk có giới hạn khóa/pham_vi riêng) mà câu hỏi chưa nêu khóa
        can_hoi_khoa = khoa is None and any(
            ("pham_vi" in d["chunk"] or "khoa_tuyen_tu" in d["chunk"] or "khoa_tuyen_den" in d["chunk"])
            for _, d in ket_qua
        )

        canh_bao = None
        if ngoai_khoa and ket_qua:
            canh_bao = (
                f"Chưa có quy định áp dụng cho khóa {khoa} trong dữ liệu (các văn bản tìm được "
                f"áp dụng cho khóa khác). Hãy hỏi Phòng Đào tạo."
            )

        return {
            "canh_bao": canh_bao,
            "nganh": sorted(nganh),
            "chuong_trinh": sorted(chuong_trinh),
            "can_hoi_lai": can_hoi_lai,
            "can_hoi_khoa": can_hoi_khoa,
            "khoa_tuyen": khoa,
            "ket_qua": [
                {
                    "diem": round(diem, 2),
                    "chunk_id": d["chunk"]["chunk_id"],
                    "nhom_chuan": d["vb"].get("nhom_chuan"),
                    "pham_vi": _nhan_khoa(d["quy_tac"]),
                    "trich_dan": trich_dan(d["chunk"], d["vb"]),
                    "text": d["chunk"]["text"],
                    "chung_chi_toi_thieu": d["chunk"].get("chung_chi_toi_thieu"),
                }
                for diem, d in ket_qua
            ],
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--top", type=int, default=2)
    ap.add_argument(
        "--full",
        action="store_true",
        help="in nguyên văn chunk (mặc định cắt 500 ký tự)",
    )
    ap.add_argument("queries", nargs="*")
    args = ap.parse_args()

    r = KeywordRetriever(args.data)

    def hoi(q: str) -> None:
        out = r.search(q, top_k=args.top)
        print(f"\n? {q}")
        print(f"   ngành={out['nganh']} chương trình={out['chuong_trinh']} khóa={out['khoa_tuyen']}")
        if out["canh_bao"]:
            print("   CẢNH BÁO: " + out["canh_bao"])
        if out["can_hoi_lai"]:
            print(
                "   Lưu ý: mức điểm khác nhau theo chương trình/ngành, "
                "hãy nêu chương trình (tăng cường, tiên tiến, đại trà, cử nhân tài năng) và ngành để có đáp án chính xác."
            )
        if out["can_hoi_khoa"]:
            print("   Lưu ý: quy định khác nhau theo khóa tuyển, hãy nêu khóa (ví dụ: khóa 2023).")
        if not out["ket_qua"]:
            print("   (không tìm thấy chunk phù hợp)")
        tu_khoa = set(tach_tu(q)) - STOPWORDS
        for k in out["ket_qua"]:
            print(f"\n   {k['trich_dan']}   (độ phù hợp {k['diem']})")
            print(f"    [phạm vi: {k['pham_vi']}]")
            cc = k.get("chung_chi_toi_thieu")
            if cc:
                chon = {
                    ten: gt for ten, gt in cc.items() if tach_tu(ten)[0] in tu_khoa
                }
                for ten, gt in (chon or cc).items():
                    print(f"    - {ten}: {gt}")
            else:
                van = (
                    k["text"]
                    if args.full or len(k["text"]) <= 500
                    else k["text"][:500] + " ..."
                )
                print("    " + van.replace("\n", "\n    "))

    if args.queries:
        for q in args.queries:
            hoi(q)
    else:
        print("Nhập câu hỏi (Enter để trống để thoát)")
        while True:
            q = input("> ").strip()
            if not q:
                break
            hoi(q)


if __name__ == "__main__":
    main()
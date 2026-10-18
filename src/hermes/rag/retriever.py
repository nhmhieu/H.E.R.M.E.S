from __future__ import annotations

import argparse  # đọc tham số dòng lệnh
import json
import math
import re        # regex tìm alies và tách từ
import unicodedata    # xử lý dấu tiếng việt
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
}

STOPWORDS = {
    "la", "cua", "va", "hoac", "co", "khong", "bao", "nhieu", "can", "phai",
    "de", "thi", "cho", "em", "minh", "toi", "ban", "nao", "gi", "the", "nhu",
    "duoc", "o", "trong", "khi", "nay", "do", "hoc", "nganh", "a", "b", "c", "sao",
}

# Sinh viên hỏi bằng ngôn ngữ đời thường, văn bản dùng thuật ngữ chính thức.
# Khóa = cụm từ (đã bỏ dấu) trong câu hỏi; giá trị = các từ được THÊM vào truy vấn (không thay thế).
MO_RONG = {
    "rot mon": "khong dat hoc lai", "rot": "khong dat hoc lai", "truot": "khong dat hoc lai",
    "bi f": "khong dat hoc lai thang diem diem chu",
    "diem f": "khong dat hoc lai thang diem diem chu", "thi lai": "hoc lai hoan thi",
    "dtb": "diem trung binh", "diem tb": "diem trung binh", "gpa": "diem trung binh tich luy",
    "cpa": "diem trung binh tich luy", "hoc luc": "xep loai diem trung binh",
    "xep loai": "diem trung binh xuat sac gioi kha", "xep hang": "diem trung binh tich luy xuat sac gioi",
    "duoi hoc": "buoc thoi hoc", "bi duoi": "buoc thoi hoc", "bo hoc": "buoc thoi hoc tu y bo hoc",
    "ra truong": "tot nghiep", "bang cap": "bang tot nghiep",
    "bao luu": "nghi hoc tam thoi bao luu ket qua", "tam nghi": "nghi hoc tam thoi",
    "mien mon": "mien hoc cong nhan chuyen doi tin chi", "mien hoc": "cong nhan ket qua chuyen doi tin chi",
    "song nganh": "hoc cung luc hai chuong trinh", "hai nganh": "hoc cung luc hai chuong trinh",
    "bang hai": "hoc cung luc hai chuong trinh", "bang 2": "hoc cung luc hai chuong trinh",
    "chuyen nganh": "chuyen chuong trinh", "online": "truc tuyen",
    "dkhp": "dang ky hoc phan", "dang ky mon": "dang ky hoc phan", "mon hoc": "hoc phan",
    "hoc vuot": "dang ky vuot so tin chi toi da", "thi ho": "thi ho dinh chi hoc tap ky luat",
    "gian lan": "gian lan thi ky luat", "do an": "do an tot nghiep khoa luan",
    "khoa luan": "khoa luan tot nghiep do an", "hoc toi da": "thoi gian toi da hoan thanh khoa hoc",
}


def mo_rong(q: str) -> list[str]:
    them = []
    for k in sorted(MO_RONG, key=len, reverse=True):
        if re.search(rf"\b{k}\b", q):
            them += MO_RONG[k].split()
    return them


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())  # tách ký tự có dấu thanh chữ gốc và dấu
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # duyệt các kí tự trừ dấu
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
            head = " ".join([
                c["ten_dieu"], c["chu_de"], vb["ten_van_ban"],
                vb["chuong_trinh"], " ".join(vb.get("chuong_trinh_alias", [])),
            ])
            self.docs.append({
                "chunk": c,
                "vb": vb,
                "tf": Counter(tach_tu(c["text"])),  # tần suất từ trong nội dung
                "head": set(tach_tu(head)),        # từ trong tiêu đề/chủ đề, được cộng thêm điểm
                # chuỗi từ liền nhau (đã bỏ dấu) để kiểm tra cụm "buoc thoi hoc", "hoc lai"...
                "norm": " " + " ".join(tach_tu(f"{c['ten_dieu']} {c['chu_de']} {c['text']}")) + " ",
            })

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
        # "khóa 2023": lấy ra để cảnh báo, không đưa vào từ khóa tìm kiếm
        m_khoa = re.search(r"\bkhoa\s+(20\d\d)\b", q)
        khoa = int(m_khoa.group(1)) if m_khoa else None
        if m_khoa:
            q = q.replace(m_khoa.group(0), " ")
        nganh, q = nhan_dien(q, ALIAS_NGANH)
        chuong_trinh, q = nhan_dien(q, ALIAS_CHUONG_TRINH)
        day_tu = re.findall(r"[a-z0-9]+", q)
        w_tok = {t: 1.0 for t in day_tu if t not in STOPWORDS}
        for t in mo_rong(q):  # từ suy ra từ từ đồng nghĩa chỉ tính nửa trọng số
            if t not in STOPWORDS:
                w_tok.setdefault(t, 0.5)
        tokens = set(w_tok)
        # từ lạ (không có trong kho dữ liệu) = tín hiệu câu hỏi ngoài phạm vi
        max_w = max((v ** 2 for v in self.idf.values()), default=0.0)
        tong_w = sum(w_tok[t] * (self.idf[t] ** 2 if t in self.idf else max_w) for t in tokens)
        # cặp từ liền nhau trong câu hỏi (bỏ cặp gồm toàn từ dừng)
        cap_tu = [(a, b) for a, b in zip(day_tu, day_tu[1:]) if not (a in STOPWORDS and b in STOPWORDS)]

        # độ hiếm của từng cụm 2 từ (vd. "thi ho" chỉ có ở vài chunk -> thưởng lớn; "bi xu" phổ biến -> nhỏ)
        cum_hiem = []
        for a, b in cap_tu:
            cum = f" {a} {b} "
            if cum not in self._df_cum:
                self._df_cum[cum] = sum(1 for d in self.docs if cum in d["norm"])
            df_c = self._df_cum[cum]
            if df_c:
                cum_hiem.append((cum, math.log(1 + (len(self.docs) - df_c + 0.5) / (df_c + 0.5))))

        # loc theo metadata
        ung_vien = [
            d for d in self.docs
            if (not nganh or not d["vb"]["nganh"] or any(n in d["vb"]["nganh"] for n in nganh))
            and (not chuong_trinh or not d["vb"].get("chuong_trinh")
                 or d["vb"]["chuong_trinh"] in chuong_trinh)
        ]

        ket_qua = []
        for d in ung_vien:
            diem = 0.0
            khop = 0.0
            for t in tokens:
                if t not in self.idf:
                    continue
                trong_so = w_tok[t] * self.idf[t] ** 2    # bình phương: từ hiếm (ielts, toeic...) áp đảo từ chung
                tf = d["tf"].get(t, 0)
                if tf or t in d["head"]:
                    khop += trong_so
                if tf:
                    diem += trong_so * (1 + math.log(tf))
                if t in d["head"]:
                    diem += trong_so * 1.5
            for cum, idf_cum in cum_hiem:  # thưởng khi cả cụm xuất hiện liền nhau, theo độ hiếm của CỤM
                if cum in d["norm"]:
                    diem += idf_cum ** 2
            # độ phủ: phần trọng số của câu hỏi mà chunk này khớp được (câu ngoài phạm vi thường < 0.35)
            if diem > 0 and (tong_w == 0 or khop / tong_w >= min_coverage):
                ket_qua.append((diem, d))

        def loc(ds):  # sắp xếp + bỏ điểm quá thấp (tuyệt đối min_score, hoặc so với kết quả đầu min_ratio)
            ds = sorted(ds, key=lambda x: x[0], reverse=True)
            if not ds:
                return ds
            nguong = max(min_score, min_ratio * ds[0][0])
            return [x for x in ds if x[0] >= nguong]

        if nganh or chuong_trinh:       # người dùng nêu ngành/chương trình: ưu tiên nhẹ văn bản riêng của ngành
            ket_qua = [(diem * 1.5 if d["vb"]["nganh"] else diem, d) for diem, d in ket_qua]
        ket_qua = loc(ket_qua)[:top_k]

        # khong nêu ngành và kết quả dấn đến nhiều chuẩn khác nhau thì nên hỏi lại
        nhom = {d["vb"].get("nhom_chuan") for _, d in ket_qua
                if d["chunk"].get("chung_chi_toi_thieu")} - {None}  # chỉ hỏi lại khi các mức điểm khác nhau
        can_hoi_lai = not nganh and len(nhom) > 1

        canh_bao = None
        if khoa:
            for _, d in ket_qua:
                m = re.search(r"\b(20\d\d)\b", str(d["vb"].get("khoa_tuyen", "")))
                if m and khoa < int(m.group(1)):
                    canh_bao = (f"{d['vb']['loai']} {d['vb']['so_hieu']} chỉ áp dụng cho khóa tuyển {m.group(1)} "
                                f"trở đi, chưa có dữ liệu cho khóa {khoa}. Hãy hỏi Phòng Đào tạo.")
                    break

        return {
            "canh_bao": canh_bao,
            "nganh": sorted(nganh),
            "chuong_trinh": sorted(chuong_trinh),
            "can_hoi_lai": can_hoi_lai,
            "ket_qua": [
                {
                    "diem": round(diem, 2),
                    "chunk_id": d["chunk"]["chunk_id"],
                    "nhom_chuan": d["vb"].get("nhom_chuan"),
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
    ap.add_argument("--full", action="store_true", help="in nguyên văn chunk (mặc định cắt 500 ký tự)")
    ap.add_argument("queries", nargs="*")
    args = ap.parse_args()

    r = KeywordRetriever(args.data)

    def hoi(q: str) -> None:
        out = r.search(q, top_k=args.top)
        print(f"\n? {q}")
        print(f"   ngành={out['nganh']} chương trình={out['chuong_trinh']}")
        if out["canh_bao"]:
            print("   CẢNH BÁO: " + out["canh_bao"])
        if out["can_hoi_lai"]:
            print("   Lưu ý: chưa biết bạn học ngành nào. Mức điểm khác nhau theo ngành, "
                  "hãy nêu ngành để có đáp án chính xác.")
        if not out["ket_qua"]:
            print("   (không tìm thấy chunk phù hợp)")
        tu_khoa = set(tach_tu(q)) - STOPWORDS
        for k in out["ket_qua"]:
            print(f"\n   {k['trich_dan']}   (độ phù hợp {k['diem']})")
            cc = k.get("chung_chi_toi_thieu")
            if cc:
                chon = {ten: gt for ten, gt in cc.items() if tu_khoa & set(tach_tu(ten))}
                for ten, gt in (chon or cc).items():
                    print(f"    - {ten}: {gt}")
            else:
                van = k["text"] if args.full or len(k["text"]) <= 500 else k["text"][:500] + " ..."
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

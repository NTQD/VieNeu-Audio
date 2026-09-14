"""Xuat toan bo Character/Terminology Glossary dang luu trong ChromaDB
(voxdirector/glossary/store.py) ra CSV va/hoac 1 trang HTML co the mo bang
trinh duyet - "muc toi thieu" cua yeu cau "ChromaDB Data Visualizer": doc
bang mat thuong duoc du lieu dang co trong glossary MA KHONG can chay ca web
UI, dung khi kiem tra nhanh/debug hoac chia se cho nguoi khong co quyen truy
cap server.

Day la READ-ONLY (chi xuat, khong sua/xoa) - muon THEM/SUA/XOA entry, dung
Glossary manager tren web UI (Cai dat du lieu > "Glossary dang dung", goi
GET/POST/DELETE /api/glossary - xem backend/app/main.py) hoac sua truc tiep
qua voxdirector.glossary.store trong 1 script/shell rieng.

Chay: python scripts/export_chromadb_glossary.py [--format csv|html|both]
                                                  [--out-dir data/exports]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from voxdirector.glossary.store import list_entries

_COLUMN_ORDER = [
    "original_term",
    "canonical_form",
    "entity_type",
    "first_seen_chapter",
    "pronunciation_note",
]
_COLUMN_LABELS_VI = {
    "original_term": "Tên gốc",
    "canonical_form": "Tên chuẩn hoá",
    "entity_type": "Loại",
    "first_seen_chapter": "Chương xuất hiện",
    "pronunciation_note": "Ghi chú phát âm",
}


def build_dataframe() -> pd.DataFrame:
    """Chuyen list_entries() (list[dict], tu ChromaDB metadatas) thanh 1
    DataFrame co thu tu cot on dinh - metadatas tra ve tu ChromaDB KHONG dam
    bao thu tu key, nen ep lai theo _COLUMN_ORDER de CSV/HTML luon nhat quan
    giua cac lan xuat, du glossary rong hay co nhieu entry."""
    entries = list_entries()
    if not entries:
        return pd.DataFrame(columns=_COLUMN_ORDER)
    df = pd.DataFrame(entries)
    for col in _COLUMN_ORDER:
        if col not in df.columns:
            df[col] = None
    df = df[_COLUMN_ORDER].sort_values("original_term", na_position="last").reset_index(drop=True)
    return df


def export_csv(df: pd.DataFrame, out_path: str) -> None:
    df.to_csv(out_path, index=False, encoding="utf-8-sig")  # utf-8-sig: Excel tren Windows mo dung dau tieng Viet


def export_html(df: pd.DataFrame, out_path: str) -> None:
    display_df = df.rename(columns=_COLUMN_LABELS_VI)
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>VoxDirector - Glossary (ChromaDB export)</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.25rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
  th {{ background: #f3f3f3; position: sticky; top: 0; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .count {{ color: #666; font-size: 0.85rem; margin-bottom: 1rem; }}
</style>
</head>
<body>
<h1>VoxDirector — Glossary đang dùng (ChromaDB)</h1>
<p class="count">{len(display_df)} entry — xuất read-only, không sửa/xoá được từ trang này.
Muốn sửa: dùng "Glossary đang dùng" trong Cài đặt dữ liệu trên web UI.</p>
{display_df.to_html(index=False, na_rep="", escape=True)}
</body>
</html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["csv", "html", "both"], default="both")
    parser.add_argument(
        "--out-dir",
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "exports"),
    )
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    df = build_dataframe()
    print(f"Đọc được {len(df)} entry từ ChromaDB glossary.")

    if args.format in ("csv", "both"):
        csv_path = os.path.join(args.out_dir, "glossary.csv")
        export_csv(df, csv_path)
        print(f"Đã ghi CSV: {csv_path}")

    if args.format in ("html", "both"):
        html_path = os.path.join(args.out_dir, "glossary.html")
        export_html(df, html_path)
        print(f"Đã ghi HTML: {html_path}")


if __name__ == "__main__":
    main()

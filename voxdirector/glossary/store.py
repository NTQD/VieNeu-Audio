"""ChromaDB setup + truy xuất cho Character/Terminology Glossary (dùng bởi
Agent Beta để giữ nhất quán tên riêng/địa danh/thuật ngữ xuyên suốt truyện).
"""

from voxdirector.config import (
    CHROMA_PERSIST_DIR,
    GLOSSARY_COLLECTION_NAME,
    GLOSSARY_EMBEDDING_MODEL,
    GLOSSARY_TOP_K,
)
from voxdirector.glossary.schema import GlossaryEntry

_client = None
_collection = None


def _get_collection():
    """Lấy (hoặc tạo mới) collection ChromaDB, cache lại — chỉ khởi tạo 1
    lần. Dùng sentence-transformers/all-MiniLM-L6-v2 chạy LOCAL (không gọi
    API trả phí nào) để embed — đúng yêu cầu spec: không phụ thuộc paid
    embedding API cho việc này."""
    global _client, _collection
    if _collection is None:
        import chromadb
        from chromadb.utils import embedding_functions

        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=GLOSSARY_EMBEDDING_MODEL
        )
        _collection = _client.get_or_create_collection(
            name=GLOSSARY_COLLECTION_NAME, embedding_function=embed_fn,
        )
    return _collection


def _entry_doc_text(entry: GlossaryEntry) -> str:
    """Văn bản dùng để embed 1 glossary entry — gồm term gốc + canonical
    form để truy vấn theo cả 2 chiều (tên gốc hoặc tên đã chuẩn hoá)."""
    return f"{entry.original_term} {entry.canonical_form}"


def add_entry(entry: GlossaryEntry) -> None:
    """Thêm/ghi đè 1 entry vào glossary (id = original_term — mỗi tên gốc
    chỉ có đúng 1 canonical_form tại một thời điểm)."""
    collection = _get_collection()
    collection.upsert(
        ids=[entry.original_term],
        documents=[_entry_doc_text(entry)],
        metadatas=[entry.model_dump(exclude_none=True)],
    )


def list_entries() -> list[dict]:
    """Liet ke TOAN BO entry hien co trong glossary (khong can query_texts -
    dung collection.get() thay vi collection.query(), khong yeu cau embed gi
    ca). Phuc vu 2 muc dich: (1) trang quan ly Glossary "dang dung" tren UI
    (khac voi "Glossary khoi tao" - file JSON seed tinh, xem
    frontend/src/components/SettingsPanel.tsx), sua duoc CHINH XAC nhung gi
    Beta dang thuc su tra cuu, bao gom ca entry duoc duyet qua "Duyet" o
    NewTermConfirmationPanel; (2) scripts/export_chromadb_glossary.py.

    Tra ve list rong neu glossary chua co entry nao - trang thai binh thuong."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    result = collection.get(include=["metadatas"])
    return list(result.get("metadatas") or [])


def delete_entry(original_term: str) -> bool:
    """Xoa 1 entry theo original_term (= id trong ChromaDB, xem add_entry()).
    Tra ve False (khong loi) neu term khong ton tai - xoa 1 thu khong co san
    la trang thai binh thuong (vd. nguoi dung bam xoa 2 lan/tab khac da xoa
    truoc), khong phai loi can bao."""
    collection = _get_collection()
    existing = collection.get(ids=[original_term])
    if not existing.get("ids"):
        return False
    collection.delete(ids=[original_term])
    return True


def seed_entries(entries: list[GlossaryEntry]) -> None:
    """Nạp nhiều entry cùng lúc — dùng khi test hoặc khởi tạo glossary ban đầu."""
    for entry in entries:
        add_entry(entry)


def seed_from_file(path=None) -> int:
    """Nạp glossary seed từ data/glossary_seed.json (Section 6.3 của spec —
    team-uploaded qua POST /api/settings/glossary-seed, KHÔNG hardcode).
    path=None dùng config.GLOSSARY_SEED_PATH mặc định.

    Trả về số entry đã nạp. File với "entries": [] (hoặc chưa từng upload
    gì) là trạng thái bình thường ở chương đầu tiên — không phải lỗi, xem
    query_glossary()."""
    import json

    from voxdirector.config import GLOSSARY_SEED_PATH

    load_path = path or GLOSSARY_SEED_PATH
    with open(load_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = [GlossaryEntry(**e) for e in data.get("entries", [])]
    seed_entries(entries)
    return len(entries)


def query_glossary(chapter_text: str, top_k: int = GLOSSARY_TOP_K) -> list[dict]:
    """Truy xuất top-k glossary entry liên quan nhất tới nội dung 1 chương —
    dùng làm glossary_context truyền vào Agent Beta trước khi gọi LLM.

    Trả về list rỗng nếu glossary chưa có entry nào (chương đầu tiên, chưa
    tích luỹ được gì) — đây là trạng thái bình thường, không phải lỗi.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []
    result = collection.query(
        query_texts=[chapter_text], n_results=min(top_k, collection.count()),
    )
    metadatas = result.get("metadatas", [[]])[0]
    return list(metadatas)

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


def seed_entries(entries: list[GlossaryEntry]) -> None:
    """Nạp nhiều entry cùng lúc — dùng khi test hoặc khởi tạo glossary ban đầu."""
    for entry in entries:
        add_entry(entry)


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

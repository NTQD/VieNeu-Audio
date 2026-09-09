"""LangGraph wiring: Alpha -> Beta -> [existing normalizer/splitter] ->
Gamma -> [existing TTS/postprocess/subtitle/video] -> Delta.

Đây là graph THAM KHẢO/ĐỘC LẬP để chạy Alpha -> Beta -> normalizer ->
splitter -> Gamma qua CLI/script, tách biệt khỏi vòng lặp Gradio trong
pipeline/auto_tts.py.

pipeline/auto_tts.py (đường dẫn CHÍNH khi dùng qua giao diện web) đã tự gọi
TRỰC TIẾP Alpha (segment_chapters) và Beta (run_beta, qua _apply_beta) theo
đúng thứ tự Alpha -> Beta -> normalizer, KHÔNG đi qua graph này — lý do:
Gradio dùng mô hình request/callback đồng bộ theo từng nút bấm và cần báo
tiến trình (progress_cb) theo từng lô khi render audio hàng trăm phần, không
khớp tự nhiên với 1 StateGraph chạy gọn từ đầu đến cuối rồi mới trả kết quả.
Gọi trực tiếp giúp dễ debug hơn — đúng theo lựa chọn spec cho phép ("Implement
chapter iteration as a loop... or as a LangGraph subgraph — either is
acceptable; prioritize whichever is simpler to debug").

graph.py này hữu ích khi cần: (a) test end-to-end Alpha->Beta->Gamma ngoài
UI, (b) entry point độc lập cho môi trường không cần Gradio (vd. 1 batch job
chạy trên server, không mở giao diện web).

Delta (QA) và bước render TTS/postprocess/video KHÔNG có trong graph này —
2 phần đó phụ thuộc engine TTS đã nạp sẵn (biến toàn cục `tts`/`selected_voice`
trong pipeline/auto_tts.py) và các file .wav thực sự đã render ra đĩa, không
phải thứ 1 StateGraph thuần tuý nên tự tạo ra được. Delta được gọi trực tiếp
từ pipeline/auto_tts.py SAU khi audio đã render xong (xem _apply_delta ở đó).
"""

from voxdirector.agents.alpha_ingestion import segment_chapters
from voxdirector.agents.beta_consistency import run_beta
from voxdirector.agents.gamma_prosody import tag_segments
from voxdirector.agents.state import VoxDirectorState


def node_alpha(state: VoxDirectorState) -> dict:
    chapters = segment_chapters(state["raw_text"])
    return {"chapters": chapters, "current_chapter_index": 0}


def node_beta(state: VoxDirectorState) -> dict:
    chapter = state["chapters"][state["current_chapter_index"]]
    result = run_beta(chapter["text"], chapter_number=state["current_chapter_index"] + 1)
    return {"corrected_text": result["corrected_text"]}


def node_normalize(state: VoxDirectorState) -> dict:
    from text_normalizer import normalize_text_for_tts

    return {"normalized_text": normalize_text_for_tts(state["corrected_text"])}


def node_split(state: VoxDirectorState) -> dict:
    from text_splitter import split_text_for_tts

    return {"split_chunks": split_text_for_tts(state["normalized_text"], 250)}


def node_gamma(state: VoxDirectorState) -> dict:
    tagged = []
    for chunk in state["split_chunks"]:
        tagged.extend(tag_segments(chunk))
    return {"tagged_segments": tagged}


def build_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(VoxDirectorState)
    graph.add_node("alpha", node_alpha)
    graph.add_node("beta", node_beta)
    graph.add_node("normalize", node_normalize)
    graph.add_node("split", node_split)
    graph.add_node("gamma", node_gamma)

    graph.set_entry_point("alpha")
    graph.add_edge("alpha", "beta")
    graph.add_edge("beta", "normalize")
    graph.add_edge("normalize", "split")
    graph.add_edge("split", "gamma")
    graph.add_edge("gamma", END)

    return graph.compile()


def run_ingestion_pipeline(raw_text: str) -> VoxDirectorState:
    """Chạy Alpha -> Beta -> normalizer -> splitter -> Gamma trên chương ĐẦU
    TIÊN mà Alpha tách được từ raw_text — dùng để test/demo pipeline agent
    ngoài giao diện Gradio. Không render audio/video/QA (xem docstring module
    ở trên)."""
    import sys, os

    pipeline_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline")
    if pipeline_dir not in sys.path:
        sys.path.insert(0, pipeline_dir)

    app = build_graph()
    return app.invoke({"raw_text": raw_text})

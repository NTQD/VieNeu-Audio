"""Step 3 (isolated, live) - test Agent Alpha THAT voi Gemini API thuc su.
KHONG commit key vao repo - doc tu file tam trong thu muc scratchpad ngoai
repo, KHONG bao gio in lai key ra man hinh/log.

Chay: python scratch_check/test_agent_alpha_live.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

KEY_FILE = (
    r"C:\Users\admin\AppData\Local\Temp\claude\E--tool-audio-VieNeu-TTS--"
    r"claude-worktrees-tts-colab-gpu-performance-5c6608\0a628a73-c803-433c-"
    r"b507-edb2c0f40485\scratchpad\gemini_key.txt"
)
with open(KEY_FILE, "r", encoding="utf-8") as f:
    # .strip() quan trong - loi ro ri key 2 lan truoc trong phien nay la vi
    # khoang trang thua lam httpx tu che Authorization header trong exception.
    os.environ["GEMINI_API_KEY"] = f.read().strip()

from voxdirector.agents.alpha_ingestion import segment_chapters

SAMPLE_WITH_HEADING = """\
Chương 1: Khởi Đầu

Lý Phong tỉnh dậy giữa một khu rừng xa lạ, xung quanh chỉ toàn sương mù dày \
đặc. Hắn nhớ rằng trước đó mình vừa gặp tai nạn xe hơi trên đường về nhà, \
vậy mà giờ đây lại đứng giữa nơi hoang vu này. Trong tay hắn xuất hiện một \
viên ngọc màu xanh biếc, phát ra ánh sáng nhè nhẹ.

"Đây là đâu?" Lý Phong tự hỏi, giọng run rẩy vì sợ hãi.

Chương 2: Gặp Gỡ

Ba ngày sau, Lý Phong đã quen dần với việc sinh tồn trong rừng sâu. Một buổi \
sáng nọ, hắn gặp được một lão đạo sĩ râu tóc bạc phơ đang ngồi thiền bên \
dòng suối.

"Tiểu tử, ngươi không thuộc về nơi này," lão đạo sĩ mở mắt, nhìn thẳng vào \
Lý Phong."""

SAMPLE_NO_HEADING = """\
Trời còn chưa sáng hẳn, sương giăng kín mặt hồ. Tiểu Yến ngồi co ro bên bờ, \
tay ôm chặt bọc hành lý cũ kỹ. Nàng đã trốn khỏi nhà họ Trương suốt cả đêm, \
đôi chân giờ đã rớm máu vì đi bộ qua mấy dặm đường rừng. Xa xa, tiếng gà gáy \
vọng lại báo hiệu một ngày mới sắp bắt đầu, nhưng với nàng, đó lại là nỗi lo \
sợ bị truy đuổi tiếp tục.

Buổi tối hôm đó, tại một quán trọ nhỏ cách đó hơn năm mươi dặm, Trần Vũ đang \
ngồi nhâm nhi chén rượu, ánh mắt dán chặt vào tấm bản đồ trải trên bàn. Hắn \
là thợ săn tiền thưởng nổi tiếng nhất vùng Giang Nam, và nhiệm vụ lần này - \
truy tìm một cô gái trốn khỏi nhà họ Trương - nghe có vẻ đơn giản hơn nhiều \
so với những gì hắn tưởng tượng."""


def _run(label, text):
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    print(f"(độ dài văn bản: {len(text)} ký tự)")
    try:
        chapters = segment_chapters(text)
    except Exception as e:
        # In message nhung REDACT key neu no vo tinh xuat hien trong do (phong
        # truong hop loi HTTP/SDK nhet URL/header chua key vao message - da
        # xay ra that voi HF_TOKEN truoc do trong phien nay).
        key = os.environ.get("GEMINI_API_KEY", "")
        msg = str(e)
        if key:
            msg = msg.replace(key, "[REDACTED_API_KEY]")
        print(f"LOI khi goi Agent Alpha: {type(e).__name__}: {msg}")
        return
    print(f"Số chương phát hiện: {len(chapters)}")
    for i, c in enumerate(chapters):
        preview = c["text"][:60].replace("\n", " ")
        print(f"  [{i}] start={c['start_index']} end={c['end_index']} "
              f"confidence={c['confidence_score']:.2f} needs_review={c['needs_review']}")
        print(f"      text preview: {preview!r}...")


def main():
    _run("MẪU 1: CÓ heading 'Chương N' tường minh", SAMPLE_WITH_HEADING)
    _run("MẪU 2: KHÔNG có heading - phải suy đoán ranh giới ngữ nghĩa", SAMPLE_NO_HEADING)


if __name__ == "__main__":
    main()

"""So sanh do dai audio thuc te (words/sec) theo KICH THUOC CHUNK khac nhau,
voi n_ctx=4096 (da fix) - tim so tu/chunk toi da de KHONG bi cat ngan."""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import auto_tts
from text_splitter import split_text_for_tts

PARAGRAPHS = [
    "Lý Phong tỉnh dậy giữa một khu rừng xa lạ, xung quanh chỉ toàn sương mù dày đặc. Hắn nhớ rằng trước đó mình vừa gặp tai nạn, vậy mà giờ đây lại đứng giữa nơi hoang vu này. Trong tay hắn xuất hiện một viên ngọc màu xanh biếc, phát ra ánh sáng nhè nhẹ. Đây là đâu, Lý Phong tự hỏi, giọng run rẩy vì sợ hãi.",
    "Ba ngày sau, Lý Phong đã quen dần với việc sinh tồn trong rừng sâu. Một buổi sáng nọ, hắn gặp được một lão đạo sĩ râu tóc bạc phơ đang ngồi thiền bên dòng suối. Tiểu tử, ngươi không thuộc về nơi này, lão đạo sĩ mở mắt, nhìn thẳng vào Lý Phong.",
    "Ta thuộc Hắc Vân Môn, một môn phái tu tiên đã tồn tại hàng ngàn năm. Ngươi có ý định gia nhập không? Lý Phong ngẫm nghĩ một lúc rồi gật đầu đồng ý. Từ ngày gia nhập Hắc Vân Môn, Lý Phong bắt đầu học các công pháp tu luyện cơ bản.",
    "Sư phụ của hắn là một trưởng lão nghiêm khắc nhưng công bằng, luôn nhắc nhở đệ tử về đạo lý trước khi truyền thụ võ công. Con đường tu tiên không phải lúc nào cũng bằng phẳng, sư phụ nói. Nhưng nếu con kiên trì, ắt sẽ có ngày thành tựu.",
]
CHAPTER_TEXT = " ".join(PARAGRAPHS * 2)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "chunk_size_repro")
os.makedirs(OUT_DIR, exist_ok=True)


def main():
    engine = auto_tts.init_tts()
    desc, vid = engine.list_preset_voices()[0]
    voice = engine.get_preset_voice(vid)
    print(f"Dung giong: {desc}")

    text_norm = auto_tts.normalize_text_for_tts(CHAPTER_TEXT)

    for max_words in [250, 130, 90]:
        chunks = split_text_for_tts(text_norm, max_words)
        # Chi test 2 chunk DAI NHAT (nhieu tu nhat) de tiet kiem thoi gian -
        # day la truong hop de bi cat ngan nhat.
        chunks_by_len = sorted(chunks, key=lambda c: -len(c.split()))[:2]
        print(f"\n=== max_words={max_words}: {len(chunks)} chunks tong, test 2 chunk dai nhat ===")
        for i, chunk in enumerate(chunks_by_len):
            n_words = len(chunk.split())
            wav = engine.infer(chunk, voice=voice)
            dur = len(wav) / engine.sample_rate
            rate = n_words / dur if dur else 0
            print(f"  chunk {i} ({n_words} tu): duration={dur:.2f}s rate={rate:.2f} words/sec")
            path = os.path.join(OUT_DIR, f"mw{max_words}_c{i}.wav")
            engine.save(wav, path)


if __name__ == "__main__":
    main()

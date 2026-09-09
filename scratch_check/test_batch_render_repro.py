"""Repro Step 3 (Batch)-specific "garbled audio" report - goi truc tiep
_render_chapter_audio() (dung engine.infer_batch() voi NHIEU phan trong 1
loi goi, giong het Batch that) qua .venv thuc su cua du an, BO QUA
Alpha/Beta (khong can GEMINI_API_KEY) vi nghi ngo nam o buoc render/ghep
audio, khong phai o Agent nao.

Chay: .venv/Scripts/python.exe scratch_check/test_batch_render_repro.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import auto_tts

# Van ban DAI de dam bao co it nhat 6-7 phan (~250 tu/phan) trong CUNG 1 loi
# goi engine.infer_batch() (BATCH_GROUP_SIZE=8) - giong het tinh huong Batch
# that (nhieu phan trong 1 chuong), khac voi Preview (1 cau ngan, 1 lan goi).
PARAGRAPHS = [
    "Lý Phong tỉnh dậy giữa một khu rừng xa lạ, xung quanh chỉ toàn sương mù dày đặc. Hắn nhớ rằng trước đó mình vừa gặp tai nạn, vậy mà giờ đây lại đứng giữa nơi hoang vu này. Trong tay hắn xuất hiện một viên ngọc màu xanh biếc, phát ra ánh sáng nhè nhẹ. Đây là đâu, Lý Phong tự hỏi, giọng run rẩy vì sợ hãi.",
    "Ba ngày sau, Lý Phong đã quen dần với việc sinh tồn trong rừng sâu. Một buổi sáng nọ, hắn gặp được một lão đạo sĩ râu tóc bạc phơ đang ngồi thiền bên dòng suối. Tiểu tử, ngươi không thuộc về nơi này, lão đạo sĩ mở mắt, nhìn thẳng vào Lý Phong.",
    "Ta thuộc Hắc Vân Môn, một môn phái tu tiên đã tồn tại hàng ngàn năm. Ngươi có ý định gia nhập không? Lý Phong ngẫm nghĩ một lúc rồi gật đầu đồng ý. Từ ngày gia nhập Hắc Vân Môn, Lý Phong bắt đầu học các công pháp tu luyện cơ bản.",
    "Sư phụ của hắn là một trưởng lão nghiêm khắc nhưng công bằng, luôn nhắc nhở đệ tử về đạo lý trước khi truyền thụ võ công. Con đường tu tiên không phải lúc nào cũng bằng phẳng, sư phụ nói. Nhưng nếu con kiên trì, ắt sẽ có ngày thành tựu.",
    "Nhiều năm trôi qua, Lý Phong đã trở thành một trong những đệ tử xuất sắc nhất của Hắc Vân Môn. Danh tiếng của hắn lan rộng khắp vùng, nhiều môn phái khác đều biết đến tên tuổi của chàng trai trẻ tài năng này.",
    "Một ngày nọ, tin tức về một trận chiến lớn sắp xảy ra giữa các môn phái khiến cả Hắc Vân Môn xôn xao. Lý Phong được lệnh dẫn đầu một đội ngũ đệ tử trẻ tuổi tham gia vào cuộc chiến đầy cam go này.",
    "Trên đường đi, họ gặp phải vô số khó khăn và thử thách, nhưng nhờ sự đoàn kết và ý chí kiên cường, cả đội đã vượt qua tất cả. Cuối cùng, họ đến được chiến trường đúng lúc trận chiến sắp bắt đầu.",
]
# Nhan len de chac chan co >= 7 phan (~250 tu/phan) trong CUNG 1 lo goi
# infer_batch() (BATCH_GROUP_SIZE=8) - 7 doan goc chi ~330 tu, chua du.
CHAPTER_TEXT = " ".join(PARAGRAPHS * 3)
print(f"Tong so tu: {len(CHAPTER_TEXT.split())}")

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "batch_repro")
os.makedirs(OUT_DIR, exist_ok=True)
prefix = "repro_ch01"


def main():
    engine = auto_tts.init_tts()
    voices = engine.list_preset_voices()
    desc, vid = voices[0]
    voice = engine.get_preset_voice(vid)
    print(f"Dung giong: {desc} ({vid})")

    auto_tts.selected_voice = voice

    text_norm = auto_tts.normalize_text_for_tts(CHAPTER_TEXT)
    log, generated_files, total_chunks = auto_tts._render_chapter_audio(
        text_norm, prefix, OUT_DIR,
        progress_cb=lambda done, total, desc: print(f"  progress: {done}/{total} - {desc}"),
    )
    print(log)
    print(f"Tong {total_chunks} phan, cac file:")
    for f in generated_files:
        exists = os.path.isfile(f)
        size = os.path.getsize(f) if exists else 0
        print(f"  {os.path.basename(f)}: exists={exists} size={size} bytes")


if __name__ == "__main__":
    main()

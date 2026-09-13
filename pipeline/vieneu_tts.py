"""Wrapper tong hop giong noi qua VieNeu-TTS (Piper da bi go bo hoan toan
2026-09-11 - dao nguoc quyet dinh dung Piper ngay 2026-09-10, quay lai
VieNeu-TTS). Thay the pipeline/piper_tts.py (da xoa).

QUAN TRONG - chay trong venv RIENG cua backend (backend/.venv), KHONG BAO
GIO trong venv chung cua repo - xem voxdirector/config.py:
EXPECTED_VIENEU_VERSION va ghi chu chi tiet o do ve ly do (venv chung co san
1 ban `vieneu` editable-install tro vao src/vieneu/ cua chinh repo nay, kien
truc CU khac han API cua ban PyPI that su can dung).

Text dua vao synthesize_to_file() co the con chua tag cam xuc dang ngoac
vuong VieNeu-TTS ho tro that (vd. "[cười]", "[thở dài]") - Beta chen truc
tiep vao noi dung, KHONG can xu ly gi them o day, VieNeu tu hieu tag inline
trong text (Section 3a cua yeu cau doi engine, xac nhan qua README:
"Emotion cues (experimental)... Inline tags are supported anywhere in the
text"). Sentinel [[PAUSE_LONG]] (Section 7.2) PHAI da bi text_splitter.py
strip truoc khi text den day - module nay khong biet/khong can biet gi ve
sentinel do, dung y nhu voi Piper truoc day (engine-agnostic).

`style` KHONG duoc truyen vao infer() - xac nhan qua README: "style is
deprecated on v3 Turbo and has no effect... whatever you pass is simply
ignored." Doc style cua tung giong (Phong cach) da duoc "nuong" san vao
chinh giong do, chon giong dung la du - xem data/voice_presets.json.
"""

from voxdirector.config import EXPECTED_VIENEU_VERSION
from voxdirector.device_utils import detect_device

_vieneu_instance = None  # khoi tao 1 lan duy nhat, dung lai cho moi request


def _check_version():
    """Xac nhan version vieneu dang chay dung ban da ghim - fail LOUD ngay
    neu lech, thay vi de loi mo ho/hanh vi sai xay ra sau do (chinh loi da
    xay ra 1 lan: venv chung dung nham ban editable-install cu 2.7.0 thay vi
    ban PyPI 3.6.4 that su can). Dung importlib.metadata (khong dua vao
    vieneu.__version__ - xac nhan module KHONG co attribute nay)."""
    import importlib.metadata

    installed = importlib.metadata.version("vieneu")
    if installed != EXPECTED_VIENEU_VERSION:
        raise RuntimeError(
            f"vieneu version KHONG khop: dang cai {installed!r}, "
            f"can dung {EXPECTED_VIENEU_VERSION!r}. Kiem tra dang chay dung "
            f"venv rieng cua backend (backend/.venv), KHONG phai venv chung "
            f"cua repo (venv chung co the co ban `vieneu` editable-install "
            f"khac hoan toan, xem voxdirector/config.py)."
        )
    return installed


def _get_instance():
    global _vieneu_instance
    if _vieneu_instance is None:
        _check_version()

        device = detect_device()
        # Step 4 (2026-09-11): CHI xac nhan CPU duoc bao cao/dung dung -
        # KHONG xay dung co che chuyen GPU/remote-worker o day, do la buoc
        # sau, tach rieng. Vieneu() tu auto-detect CPU/GPU (torch-free ONNX
        # tren CPU, PyTorch tren CUDA) - khong truyen tham so device/backend
        # ep buoc, de dung dung hanh vi mac dinh cua SDK; chi LOG lai ket
        # qua detect_device() cua chinh du an de doi chieu.
        print(f"[vieneu_tts] device_utils.detect_device() bao cao: {device} "
              f"(Vieneu() se tu auto-detect rieng, xem README)")

        from vieneu import Vieneu
        _vieneu_instance = Vieneu()
    return _vieneu_instance


def synthesize_to_file(text: str, voice_id: str, output_path: str) -> str:
    """Tong hop 1 doan text (co the con chua tag cam xuc dang [tag], da bi
    strip sentinel [[PAUSE_LONG]] tu truoc) thanh 1 file .wav qua
    VieNeu-TTS. voice_id la id giong trong data/voice_presets.json (chinh
    la ten giong that VieNeu-TTS dung cho tham so voice=). Tra ve
    output_path de dung trong chuoi goi tiep."""
    vieneu = _get_instance()
    audio = vieneu.infer(text, voice=voice_id)
    vieneu.save(audio, output_path)
    return output_path


def get_sample_rate(voice_id: str) -> int:
    """voice_id khong anh huong sample_rate (v3 Turbo luon 48kHz, co dinh
    theo README) - giu tham so de tuong thich chu ky goi cu (Piper truoc
    day CO the co sample_rate khac nhau theo tung voice/model)."""
    vieneu = _get_instance()
    return vieneu.sample_rate

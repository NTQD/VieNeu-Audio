"""Step 1 (isolated, CPU verification) - KHONG duoc goi tu pipeline chinh.

Kiem tra duong dan cai dat MAC DINH cua SDK vieneu: backbone GGUF luong tu hoa
(llama-cpp-python) + codec ONNX (onnxruntime) - hoan toan khong can torch.
Day la lua chon da chot: BO tinh nang Voice Cloning tren may CPU nay, vi
encode_reference() trong src/vieneu/base.py doi hoi torch vo dieu kien va
khong co codec ONNX nao ho tro encode_code() trong SDK hien tai.

Chay: python scratch_check/test_cpu_synthesis.py
"""
import os
import sys
import time

# Console Windows mac dinh dung cp1252, khong in duoc tieng Viet co dau -> ep
# stdout/stderr sang UTF-8 truoc khi in bat ky gi.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))

from vieneu import Vieneu

RTF_TEXT = (
    "Hôm nay là một ngày đẹp trời, ánh nắng chan hòa khắp phố phường Hà Nội. "
    "Mọi người đi lại tấp nập, trẻ em nô đùa trong công viên, còn người lớn thì "
    "ngồi uống cà phê và trò chuyện vui vẻ bên vỉa hè, tạo nên một khung cảnh vô "
    "cùng yên bình và đáng nhớ giữa lòng thành phố này."
)

EMOTION_TEXT = (
    "Cô ấy nhìn tôi rồi bật cười. [cười] Sau đó cô thở dài thật sâu. [thở dài] "
    "Anh ta hắng giọng rồi bắt đầu nói. [hắng giọng]"
)


def main():
    print("== Loading VieNeu-TTS (SDK defaults: GGUF backbone + ONNX codec, CPU) ==")
    t0 = time.perf_counter()
    tts = Vieneu(mode="standard")
    load_s = time.perf_counter() - t0
    print(f"Model load time: {load_s:.1f}s")
    print(f"is_quantized_model (GGUF backbone) = {tts._is_quantized_model}")
    print(f"is_onnx_codec = {tts._is_onnx_codec}")

    voices = tts.list_preset_voices()
    print(f"Preset voices found: {len(voices)}")
    if not voices:
        print("No preset voices available - aborting.")
        return
    desc, voice_id = voices[0]
    voice = tts.get_preset_voice(voice_id)
    print(f"Using voice: {desc} ({voice_id})")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    os.makedirs(out_dir, exist_ok=True)

    # ---- RTF test ----
    word_count = len(RTF_TEXT.split())
    print(f"\n== RTF test ({word_count} words) ==")
    t0 = time.perf_counter()
    audio = tts.infer(RTF_TEXT, voice=voice)
    synth_s = time.perf_counter() - t0
    audio_s = len(audio) / tts.sample_rate
    rtf = synth_s / audio_s if audio_s > 0 else float("inf")
    print(f"synthesis_time = {synth_s:.2f}s")
    print(f"audio_duration = {audio_s:.2f}s")
    print(f"RTF (synth/audio) = {rtf:.3f}")
    tts.save(audio, os.path.join(out_dir, "rtf_test.wav"))
    print(f"Saved -> {os.path.join(out_dir, 'rtf_test.wav')}")

    # ---- Emotion cue bracket syntax test ----
    print("\n== Emotion cue bracket syntax test ([cười]/[thở dài]/[hắng giọng]) ==")
    try:
        from text_normalizer import normalize_text_for_tts
        norm = normalize_text_for_tts(EMOTION_TEXT)
        print(f"normalize_text_for_tts() output:\n  {norm!r}")
    except Exception as e:
        print(f"(could not import pipeline's text_normalizer standalone: {e})")
        norm = EMOTION_TEXT

    from vieneu_utils.phonemize_text import phonemize_with_dict
    try:
        phon = phonemize_with_dict(norm, skip_normalize=True)
        print(f"phonemize_with_dict() output:\n  {phon!r}")
    except Exception as e:
        print(f"(phonemize_with_dict failed: {e})")

    t0 = time.perf_counter()
    audio2 = tts.infer(EMOTION_TEXT, voice=voice)
    synth2_s = time.perf_counter() - t0
    tts.save(audio2, os.path.join(out_dir, "emotion_cue_test.wav"))
    print(f"Saved -> {os.path.join(out_dir, 'emotion_cue_test.wav')} "
          f"({len(audio2)/tts.sample_rate:.2f}s audio, {synth2_s:.2f}s synth)")
    print("NOTE: whether the cues are *audibly* reflected can only be confirmed by "
          "actually listening to emotion_cue_test.wav - the normalize/phonemize output "
          "above shows structurally whether '[...]' survives as meaningful tokens or is "
          "just spoken/stripped as literal text.")

    # ---- Voice cloning test: SKIPPED per project decision ----
    print("\n== Voice cloning test: SKIPPED (decision) ==")
    print("Dropped in favor of the pure ONNX/GGUF torch-free path. encode_reference() in "
          "src/vieneu/base.py requires torch unconditionally, and the ONNX codec used here "
          "(neuphonic/neucodec-onnx-decoder-int8) has no encode_code() implementation - "
          "cloning is architecturally out of scope for this configuration, not a "
          "missing-sample-file issue.")


if __name__ == "__main__":
    main()

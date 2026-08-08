import re

def split_text_for_tts(text, max_words=250):
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        word_count = len(sentence.split())
        if current_word_count + word_count > max_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_word_count = 0

        current_chunk.append(sentence)
        current_word_count += word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

if __name__ == "__main__":
    text = "Nội dung truyện dịch của bạn ở đây..."
    result = split_text_for_tts(text, 250)
    for i, chunk in enumerate(result):
        print(f"Part {i+1} ({len(chunk.split())} từ): {chunk}\n")

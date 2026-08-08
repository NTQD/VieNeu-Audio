# Launcher script for VieNeu-Audio Pipeline

# Chạy script này từ thư mục gốc để khởi động giao diện Gradio

if __name__ == "__main__":
    # Import và chạy auto_tts thông qua package pipeline
    from pipeline.auto_tts import app
    app.launch()

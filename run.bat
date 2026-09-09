@echo off
REM ============================================================
REM  VoxDirector AI / VieNeu-Audio - cai dat + chay local (CPU)
REM ============================================================
REM Muc tieu: bat ky may Windows nao co the double-click file nay va tu
REM dong cai dat + chay giao dien Gradio, khong can biet truoc uv/pip/venv.
REM
REM Dung "uv" (trinh quan ly goi chinh thuc cua du an - xem uv.lock +
REM README.md) thay vi pip/venv thuong: uv sync se tu dong tai dung ban
REM Python duoc ghim trong .python-version (3.12) VA ton trong cac wheel
REM nguon tuy chinh khai bao trong pyproject.toml [tool.uv.sources] (vd.
REM ban prebuilt cua llama-cpp-python cho Windows) - pip thuong SE BO QUA
REM hoan toan phan [tool.uv.sources] nay.
REM
REM Duong dan local nay dung mac dinh torch-free cua SDK vieneu (backbone
REM GGUF qua llama-cpp-python + codec ONNX qua onnxruntime) - "uv sync"
REM KHONG kem "--group gpu" nen KHONG cai torch/CUDA gi ca.
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   VoxDirector AI - Setup + Run (local, CPU, dung uv)
echo ============================================================
echo Thu muc lam viec: %cd%
echo.

REM --- 0. Kiem tra dang o dung thu muc repo ---
if not exist "pyproject.toml" (
    echo [LOI] Khong tim thay pyproject.toml trong thu muc nay.
    echo File run.bat phai nam o thu muc goc cua repo VieNeu-TTS.
    pause
    exit /b 1
)

REM --- 1. Kiem tra / cai dat uv ---
where uv >nul 2>nul
if errorlevel 1 (
    echo [1/6] Chua co "uv" - dang tu dong cai dat...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [LOI] Cai dat uv that bai. Tu cai thu cong tai: https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
    REM uv cai vao %USERPROFILE%\.local\bin va tu them vao PATH nguoi dung,
    REM nhung cua so dang chay nay chua doc lai PATH moi - them thu cong de
    REM dung duoc NGAY trong lan chay nay, khong bat nguoi dung phai dong/mo
    REM lai cua so.
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    where uv >nul 2>nul
    if errorlevel 1 (
        echo [LOI] Da cai uv nhung khong thay trong PATH. Dong cua so nay, mo lai, roi chay lai run.bat.
        pause
        exit /b 1
    )
) else (
    echo [1/6] Da co san uv.
)
uv --version

REM --- 2. uv sync: cai dependencies chinh cua goi vieneu (ban CPU/minimal,
REM     KHONG --group gpu) - tu tai dung Python 3.12 theo .python-version.
echo.
echo [2/6] Dang chay "uv sync" (lan dau co the mat vai phut - tai Python
echo       3.12 rieng + bien dich llama-cpp-python neu can)...
uv sync
if errorlevel 1 (
    echo.
    echo [LOI] "uv sync" that bai.
    echo Loi thuong gap nhat: goi llama-cpp-python can 1 wheel dung san rieng
    echo cho Windows ma link tai ve hien dang BI HONG ^(404^) - day la 1 van
    echo de o phia upstream ^(GitHub release cua goi vieneu^), KHONG phai loi
    echo cua may ban. Neu gap loi ve llama-cpp-python o tren:
    echo   1. Bao lai cho nguoi phu trach du an ^(link wheel can duoc cap nhat
    echo      hoac tao lai^), VA
    echo   2. Tam thoi co the thu cai "Visual Studio Build Tools" ^(chon muc
    echo      "Desktop development with C++"^) de uv/pip tu bien dich tu
    echo      source thay vi dung wheel dung san:
    echo      https://visualstudio.microsoft.com/visual-cpp-build-tools/
    pause
    exit /b 1
)
echo [OK] uv sync hoan tat.

REM --- 3. Cai them dependencies rieng cho pipeline/ + voxdirector/ (agent) ---
echo.
echo [3/6] Dang cai dependencies rieng cho pipeline/voxdirector...
uv pip install -r pipeline_requirements.txt
if errorlevel 1 (
    echo [LOI] Cai dat pipeline_requirements.txt that bai. Xem log phia tren.
    pause
    exit /b 1
)
echo [OK] Dependencies da san sang.

REM --- 4. Kiem tra FFmpeg (bat buoc cho ghep audio/render video) ---
echo.
echo [4/6] Dang kiem tra FFmpeg...
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [CANH BAO] Khong tim thay ffmpeg trong PATH.
    echo Agent Delta va buoc ghep audio/render video SE LOI neu thieu ffmpeg.
    echo Cai bang lenh:  winget install Gyan.FFmpeg
    echo Roi DONG va MO LAI cua so nay ^(hoac khoi dong lai May tinh^) truoc khi chay tiep.
    echo.
    set /p CONTINUE_NO_FFMPEG="Van tiep tuc ma khong co ffmpeg? (y/N): "
    if /i not "!CONTINUE_NO_FFMPEG!"=="y" (
        pause
        exit /b 1
    )
) else (
    echo [OK] Da tim thay ffmpeg.
)

REM --- 5. Kiem tra GEMINI_API_KEY ---
REM Luu y ky thuat: "if A if B (...) else (...)" TRONG 1 lenh la 1 loi kinh
REM dien cua batch - else se gan vao if B (ben trong), khong phai if A (ben
REM ngoai), nen khi A la false thi CA 2 nhanh deu khong chay (da kiem chung
REM that truoc khi sua). Dung 1 bien co trung gian de tranh loi nay.
echo.
echo [5/6] Dang kiem tra GEMINI_API_KEY...
set KEY_MISSING=0
if "%GEMINI_API_KEY%"=="" if "%GOOGLE_API_KEY%"=="" set KEY_MISSING=1
if "%KEY_MISSING%"=="1" (
    echo [CANH BAO] Chua thay bien moi truong GEMINI_API_KEY ^(hoac GOOGLE_API_KEY^).
    echo Agent Alpha ^(tach chuong^) BAT BUOC can key nay - khong co se loi ngay khi chay Batch.
    echo.
    echo Cach lay key: https://aistudio.google.com/apikey
    echo Cach dat co dinh ^(chi can lam 1 lan, se nho cho nhung lan chay sau^):
    echo     setx GEMINI_API_KEY "dan-key-cua-ban-vao-day"
    echo Sau do DONG cua so nay, MO LAI, roi chay lai run.bat.
    echo.
    echo ^(Co the bo qua canh bao nay va tiep tuc - Agent Beta/Gamma/Delta van chay duoc
    echo   binh thuong ma khong can key, chi Agent Alpha se bao loi khi Batch.^)
    echo.
    pause
) else (
    echo [OK] Da tim thay GEMINI_API_KEY / GOOGLE_API_KEY.
)

REM --- 6. Khoi dong ung dung ---
echo.
echo [6/6] Dang khoi dong VoxDirector AI...
echo Mo trinh duyet tai http://localhost:7860 sau khi thay dong "Running on local URL".
echo Nhan Ctrl+C trong cua so nay de dung server.
echo.
uv run python -m pipeline.auto_tts

echo.
echo Server da dung.
pause

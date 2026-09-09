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
REM
REM QUAN TRONG: "uv sync" chi biet ve dependencies KHAI BAO trong
REM pyproject.toml - no KHONG biet gi ve pipeline_requirements.txt (buoc 3
REM ben duoi). Neu chay lai "uv sync" SAU KHI da cai pipeline_requirements.txt
REM roi, uv se coi cac goi do la "du thua ngoai y muon" va GO CHUNG RA, roi
REM buoc 3 lai phai cai lai tu dau - vua cham vua thua (da kiem chung that:
REM 1 lan chay lai "uv sync" go ra 79 goi vua cai o buoc 3, gay cham va noisy
REM log khong can thiet). Vi vay CHI chay "uv sync" 1 LAN DUY NHAT (danh dau
REM bang file .venv\.voxdirector_synced) - nhung lan chay sau bo qua thang
REM buoc nay. Neu ban vua sua pyproject.toml va can dong bo lai, xoa file
REM danh dau nay (hoac xoa ca thu muc .venv) roi chay lai run.bat.
if not exist ".venv\.voxdirector_synced" (
    echo.
    echo [2/6] Dang chay "uv sync" ^(lan dau co the mat vai phut - tai Python
    echo       3.12 rieng + bien dich llama-cpp-python neu can^)...
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
    echo. > ".venv\.voxdirector_synced"
    echo [OK] uv sync hoan tat.
) else (
    echo.
    echo [2/6] Da chay "uv sync" tu truoc, bo qua ^(xoa .venv\.voxdirector_synced neu can dong bo lai^).
)

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

REM --- 5. Kiem tra / nhap GEMINI_API_KEY ---
REM QUAN TRONG: chi CO 1 key duy nhat dung chung cho CA 4 Agent
REM (Alpha/Beta/Gamma/Delta) - KHONG phai moi Agent 1 key rieng. Xem
REM voxdirector/config.py (GEMINI_API_KEY/GEMINI_MODEL ghim cung, dung
REM chung cho moi lenh goi qua llm_client.py) va Section 6.0/7 cua spec
REM (moi Agent trong 1 lan chay PHAI dung cung 1 model/key, khong duoc
REM auto-routing khac nhau, de ket qua tai lap duoc).
REM
REM Luu y ky thuat: "if A if B (...) else (...)" TRONG 1 lenh la 1 loi kinh
REM dien cua batch - else se gan vao if B (ben trong), khong phai if A (ben
REM ngoai), nen khi A la false thi CA 2 nhanh deu khong chay (da kiem chung
REM that truoc khi sua). Dung 1 bien co trung gian de tranh loi nay.
REM
REM Nhap key truc tiep qua set /p (HIEN RA MAN HINH khi go, khong an ky
REM tu) - da thu dung PowerShell Read-Host -AsSecureString de an ky tu
REM nhung gap treo khi input khong phai tu console that (vd. khi test tu
REM dong) va rui ro treo ca script that su kho luong truoc trong moi truong
REM cmd.exe/Windows Terminal khac nhau - uu tien do tin cay hon, canh bao ro
REM cho nguoi dung thay vi dung ky thuat chua kiem chung chac chan.
echo.
echo [5/6] Dang kiem tra GEMINI_API_KEY...
set KEY_MISSING=0
if "%GEMINI_API_KEY%"=="" if "%GOOGLE_API_KEY%"=="" set KEY_MISSING=1

if "%KEY_MISSING%"=="1" (
    echo [CANH BAO] Chua thay bien moi truong GEMINI_API_KEY ^(hoac GOOGLE_API_KEY^).
    echo Ca 4 Agent ^(Alpha/Beta/Gamma/Delta^) DUNG CHUNG 1 key nay - Agent Alpha
    echo ^(tach chuong^) BAT BUOC can key de chay Batch; Beta/Gamma/Delta van chay
    echo duoc ma khong can key, chi bo qua phan lien quan Gemini cua rieng chung.
    echo.
    echo Lay key mien phi tai: https://aistudio.google.com/apikey
    echo.
    echo LUU Y: key se HIEN RA MAN HINH khi ban go ^(khong an ky tu^) - can than
    echo neu dang co nguoi khac nhin man hinh hoac dang chia se man hinh.
    echo.
    set /p ENTERED_KEY="Dan Gemini API key vao day roi Enter (de trong = bo qua): "
    if not "!ENTERED_KEY!"=="" (
        setx GEMINI_API_KEY "!ENTERED_KEY!" >nul
        set "GEMINI_API_KEY=!ENTERED_KEY!"
        echo [OK] Da luu GEMINI_API_KEY ^(setx - tu dong nho cho nhung lan chay sau, khong can nhap lai^).
    ) else (
        echo [BO QUA] Chua co key - Agent Alpha se bao loi khi chay Batch.
        echo Co the chay lai run.bat sau khi co key.
    )
) else (
    echo [OK] Da tim thay GEMINI_API_KEY / GOOGLE_API_KEY ^(dung chung cho ca 4 Agent^).
    set /p CHANGE_KEY="Doi sang key khac? (y/N): "
    if /i "!CHANGE_KEY!"=="y" (
        set /p ENTERED_KEY="Dan Gemini API key MOI vao day roi Enter: "
        if not "!ENTERED_KEY!"=="" (
            setx GEMINI_API_KEY "!ENTERED_KEY!" >nul
            set "GEMINI_API_KEY=!ENTERED_KEY!"
            echo [OK] Da cap nhat GEMINI_API_KEY.
        )
    )
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

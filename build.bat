@echo off
chcp 65001 > nul
echo ========================================================
echo   LEITOR MARKDOWN MODERNO - PIPELINE DE BUILD WINDOWS
echo ========================================================
echo.

echo [1/4] Validando sintaxe do script Python...
python -m py_compile md_reader.py
if %ERRORLEVEL% NEQ 0 (
    echo ERRO: Falha na sintaxe do arquivo md_reader.py!
    pause
    exit /b 1
)
echo Sintaxe validada com sucesso!
echo.

echo [2/4] Gerando executavel com PyInstaller (modo --onedir para abertura instantanea)...
python -m PyInstaller --noconsole --noconfirm ^
  --name LeitorMD ^
  --icon=app.ico ^
  --add-data "app.ico;." ^
  --collect-all PyQt6 ^
  --collect-all PyQt6.QtWebEngineCore ^
  --collect-all PyQt6.QtWebEngineWidgets ^
  md_reader.py

if %ERRORLEVEL% NEQ 0 (
    echo ERRO: Falha ao compilar com PyInstaller!
    pause
    exit /b 1
)
echo Build do executavel concluido em dist\LeitorMD\LeitorMD.exe!
echo.

echo Copiando documento_exemplo.md para a pasta do executavel...
copy /y documento_exemplo.md dist\LeitorMD\ > nul

echo Gerando arquivo compactado (.zip) para versao portatil...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\LeitorMD\*' -DestinationPath 'dist\LeitorMD-portable.zip' -Force"
if %ERRORLEVEL% EQU 0 (
    echo Versao portatil gerada com sucesso: dist\LeitorMD-portable.zip!
) else (
    echo AVISO: Nao foi possivel gerar o arquivo zip portatil.
)
echo.

echo [3/4] Procurando compilador do Inno Setup (ISCC.exe)...
set "ISCC_PATH="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"

if defined ISCC_PATH (
    echo Compilando instalador automaticamente com Inno Setup...
    "%ISCC_PATH%" installer.iss
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo [4/4] SUCESSO TOTAL!
        echo Instalador gerado: setup_output\LeitorMD_Setup.exe
    ) else (
        echo AVISO: Erro na compilacao do instalador Inno Setup.
    )
) else (
    echo Inno Setup nao localizado nos caminhos padrao.
    echo Para gerar o instalador LeitorMD_Setup.exe:
    echo 1. Instale o Inno Setup 6 (https://jrsoftware.org/isdl.php)
    echo 2. Abra o arquivo installer.iss e pressione Ctrl+F9
)

echo.
echo ========================================================
echo Processo finalizado com sucesso!
echo ========================================================
pause

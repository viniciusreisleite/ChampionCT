@echo off
setlocal
cd /d "%~dp0"

echo ======================================================
echo Atualizando mural: ChampionCT
echo ======================================================

where git >nul 2>nul
if errorlevel 1 (
    echo ERRO: Git nao encontrado.
    exit /b 10
)

where python >nul 2>nul
if errorlevel 1 (
    echo ERRO: Python nao encontrado.
    exit /b 11
)

echo.
echo 0. Sincronizando repositorio local com origin/main...
git fetch origin main
if errorlevel 1 (
    echo ERRO: Falha no git fetch.
    exit /b 20
)

git pull --rebase --autostash origin main
if errorlevel 1 (
    echo ERRO: Falha ao sincronizar a branch main.
    exit /b 21
)

echo.
echo 1. Baixando fotos e videos do Instagram...
python baixar_mural.py
if errorlevel 1 (
    echo ERRO: baixar_mural.py falhou.
    exit /b 30
)

echo.
echo 2. Preparando alteracoes...
git add -A
git diff --cached --quiet
if not errorlevel 1 (
    git commit -m "Atualizacao manual mural ChampionCT"
    if errorlevel 1 (
        echo ERRO: Falha ao criar commit.
        exit /b 40
    )

    echo.
    echo 3. Enviando para o GitHub...
    git push origin main
    if errorlevel 1 (
        echo Aviso: push rejeitado. Tentando sincronizar e reenviar uma vez...
        git pull --rebase --autostash origin main
        if errorlevel 1 (
            echo ERRO: Nao foi possivel reconciliar com origin/main.
            exit /b 41
        )
        git push origin main
        if errorlevel 1 (
            echo ERRO: Falha no git push.
            exit /b 42
        )
    )
) else (
    echo Nenhuma alteracao nova encontrada.
)

echo.
echo Concluido com sucesso: ChampionCT
exit /b 0

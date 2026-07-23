@echo off
setlocal EnableDelayedExpansion

rem ---------------------------------------------------------------------------
rem Aponta o share reservado do zrok para a API do Forge.
rem
rem O share e reservado: serve UM backend por vez. Se ele estiver rodando
rem apontado para outra porta (ex.: LM Studio em 1111), este script derruba o
rem processo antes de subir de novo no alvo certo.
rem
rem Uso:
rem   scripts\tunel-api.bat           sobe o tunel (fica ocupando o terminal)
rem   scripts\tunel-api.bat /check    so diagnostica, nao mexe em nada
rem ---------------------------------------------------------------------------

set "SHARE=lmstudioapi"
set "PORTA=8000"
set "ALVO=http://127.0.0.1:%PORTA%"

set "APENAS_CHECAR="
if /i "%~1"=="/check" set "APENAS_CHECAR=1"

echo.
echo === Tunel zrok -^> API do Forge ===
echo   share : %SHARE%
echo   alvo  : %ALVO%
echo.

rem --- 1. zrok esta instalado? -----------------------------------------------
where zrok >nul 2>&1
if errorlevel 1 (
    echo [ERRO] zrok nao encontrado no PATH.
    exit /b 1
)

rem --- 2. a API responde no alvo? --------------------------------------------
rem Sem isso o tunel sobe apontando para o vazio e o erro so aparece no browser.
echo [1/3] Checando a API em %ALVO%/health ...
powershell -NoProfile -Command "try { $r = Invoke-RestMethod '%ALVO%/health' -TimeoutSec 5; if ($r.service -eq 'forge-api') { Write-Host ('      OK - forge-api ' + $r.version + ', banco: ' + $r.database); exit 0 } else { Write-Host '      Responde, mas nao e a forge-api.'; exit 2 } } catch { Write-Host '      Sem resposta.'; exit 1 }"
set "API_ST=%ERRORLEVEL%"

if "%API_ST%"=="1" (
    echo.
    echo [ERRO] A API nao respondeu. Suba com: docker compose up -d api
    if not defined APENAS_CHECAR exit /b 1
)
if "%API_ST%"=="2" (
    echo.
    echo [ERRO] Outra coisa esta ocupando a porta %PORTA%.
    if not defined APENAS_CHECAR exit /b 1
)

rem --- 3. o share ja esta rodando? -------------------------------------------
echo [2/3] Procurando o share "%SHARE%" em execucao ...
powershell -NoProfile -Command "$p = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'zrok.exe' -and $_.CommandLine -match '%SHARE%' }); if (-not $p) { Write-Host '      Nenhum processo ativo.'; exit 0 }; foreach ($x in $p) { $alvo = if ($x.CommandLine -match 'override-endpoint\s+(\S+)') { $Matches[1] } else { '?' }; Write-Host ('      PID ' + $x.ProcessId + ' -> ' + $alvo) }; exit 3"
set "SHARE_ST=%ERRORLEVEL%"

if defined APENAS_CHECAR (
    echo.
    echo [3/3] Modo /check - nada foi alterado.
    exit /b 0
)

if "%SHARE_ST%"=="3" (
    echo       Derrubando ...
    powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'zrok.exe' -and $_.CommandLine -match '%SHARE%' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    rem O zrok leva um instante para liberar o registro do share no servidor.
    timeout /t 3 /nobreak >nul
)

rem --- 4. subir apontando para a API -----------------------------------------
echo [3/3] Subindo o share em %ALVO% ...
echo       (Ctrl+C encerra o tunel)
echo.
zrok share reserved %SHARE% --override-endpoint %ALVO% --headless

rem Se o zrok cair, a janela nao pode sumir levando a mensagem de erro junto:
rem sem o tunel de pe o zrok responde 502 e o sintoma aparece so no browser.
echo.
echo [!] O tunel encerrou (codigo %ERRORLEVEL%).
echo     Enquanto ele nao estiver de pe, %SHARE% responde 502.
pause

endlocal

@echo off
rem ------------------------------------------------------------
rem  Todo API Ò»¼üÆô¶¯½Å±¾£¨Ë«»÷ÔËĞĞ»òÔÚÃüÁîĞĞÖ´ĞĞ¾ù¿É£©
rem  µÈ¼ÛÃüÁî£º .\.venv\Scripts\python.exe -m uvicorn todo_api.main:app --reload
rem  ±àÂëÔ¼¶¨£º±¾ÎÄ¼şÒÔ GBK ±£´æ£¬ÖĞÎÄÌáÊ¾¸÷Êä³öÁ½ĞĞ£¨GBK ×Ö½Ú / UTF-8 ×Ö½Ú£©£¬
rem  ÕâÑù¿ØÖÆÌ¨ÎŞÂÛ´¦ÓÚ 936 »¹ÊÇ 65001 ´úÂëÒ³£¬ÖÁÉÙÓĞÒ»ĞĞÊÇ¿É¶ÁµÄ¡£
rem ------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON%" goto :run

echo.
echo ´íÎó£ºÕÒ²»µ½ĞéÄâ»·¾³ Python
echo é”™è¯¯ï¼šæ‰¾ä¸åˆ°è™šæ‹Ÿç¯å¢ƒ Python
echo %PYTHON%
echo ÇëÏÈÔÚÏîÄ¿¸ùÄ¿Â¼´´½¨ .venv ²¢°²×° requirements.txt ÖĞµÄÒÀÀµ£º
echo è¯·å…ˆåœ¨é¡¹ç›®æ ¹ç›®å½•åˆ›å»º .venv å¹¶å®‰è£… requirements.txt ä¸­çš„ä¾èµ–ï¼š
echo   1) python -m venv .venv
echo   2) .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1

:run
echo.
echo ÕıÔÚÆô¶¯ Todo API£¨uvicorn --reload£¬½ö¼àÌı±¾»ú 127.0.0.1£©...
echo æ­£åœ¨å¯åŠ¨ Todo APIï¼ˆuvicorn --reloadï¼Œä»…ç›‘å¬æœ¬æœº 127.0.0.1ï¼‰...
echo ½Ó¿ÚÎÄµµ£º http://127.0.0.1:8000/docs
echo æ¥å£æ–‡æ¡£ï¼š http://127.0.0.1:8000/docs
echo Í£Ö¹·şÎñ£º °´ Ctrl+C
echo åœæ­¢æœåŠ¡ï¼š æŒ‰ Ctrl+C
echo.
rem  ×Ô¶¯´ò¿ªÎÄµµÒ³£ºuvicorn --reload Êµ²âÔ¼ 2.4 Ãë²Å°ó¶¨¶Ë¿Ú£¬
rem  ¹Ê·Åµ½ºóÌ¨ÑÓÊ±Ô¼ 4 ÃëÔÙ¿ªä¯ÀÀÆ÷£¬±ÜÃâä¯ÀÀÆ÷ÏÈÓÚ·şÎñ¾ÍĞ÷¶ø´ò²»¿ª¡£
echo ÎÄµµÒ³½«ÔÚÔ¼ 4 Ãëºó×Ô¶¯´ò¿ª£¨Î´×Ô¶¯´ò¿ªÇëÊÖ¶¯·ÃÎÊ http://127.0.0.1:8000/docs£©
echo æ–‡æ¡£é¡µå°†åœ¨çº¦ 4 ç§’åè‡ªåŠ¨æ‰“å¼€ï¼ˆæœªè‡ªåŠ¨æ‰“å¼€è¯·æ‰‹åŠ¨è®¿é—® http://127.0.0.1:8000/docsï¼‰
start "" /b cmd /c "ping -n 5 127.0.0.1 >nul & start http://127.0.0.1:8000/docs"
"%PYTHON%" -m uvicorn todo_api.main:app --reload
echo.
echo ·şÎñÒÑÍ£Ö¹¡£
echo æœåŠ¡å·²åœæ­¢ã€‚
pause
endlocal

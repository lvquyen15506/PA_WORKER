@echo off
rem PA Worker - cap nhat phien ban moi (chep ban moi de len thu muc nay truoc). Xem docs\huong-dan-cai-dat.md
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\cap-nhat.ps1" %*

@echo off
rem PA Worker - khoi dong (lan dau thi cai dat). Xem docs\huong-dan-cai-dat.md
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\pa-worker.ps1" %*

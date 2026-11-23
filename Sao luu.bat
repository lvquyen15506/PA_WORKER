@echo off
rem PA Worker - sao luu ngay du lieu ra thu muc backups. Xem docs\huong-dan-cai-dat.md
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\sao-luu.ps1" %*

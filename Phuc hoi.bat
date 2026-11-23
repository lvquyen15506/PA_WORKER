@echo off
rem PA Worker - phuc hoi du lieu tu file sao luu trong thu muc backups. Xem docs\huong-dan-cai-dat.md
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\phuc-hoi.ps1" %*

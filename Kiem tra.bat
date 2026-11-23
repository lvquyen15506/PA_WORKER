@echo off
rem PA Worker - kiem tra nhanh tinh trang he thong. Xem docs\xu-ly-su-co.md
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\kiem-tra.ps1" %*

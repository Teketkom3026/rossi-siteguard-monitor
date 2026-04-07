@echo off
echo ============================================
echo  Rossi SiteGuard Monitor — Windows EXE Build
echo ============================================

echo Installing dependencies...
pip install pyinstaller pyqt6 httpx keyring cryptography

echo Building EXE...
cd ..
pyinstaller --onefile --windowed --name RossiSiteGuardMonitor ^
  --add-data "resources;resources" ^
  --add-data "core;core" ^
  --add-data "ui;ui" ^
  --hidden-import PyQt6.QtCore ^
  --hidden-import PyQt6.QtWidgets ^
  --hidden-import PyQt6.QtGui ^
  --hidden-import PyQt6.sip ^
  --hidden-import httpx ^
  --hidden-import httpx._transports ^
  --hidden-import httpx._transports.default ^
  --hidden-import cryptography ^
  --hidden-import cryptography.fernet ^
  --hidden-import cryptography.hazmat ^
  --hidden-import cryptography.hazmat.primitives ^
  --hidden-import cryptography.hazmat.backends ^
  --hidden-import keyring ^
  --hidden-import keyring.backends ^
  --hidden-import keyring.backends.Windows ^
  --exclude-module tkinter ^
  --exclude-module matplotlib ^
  --exclude-module numpy ^
  main.py

echo.
echo Build complete! EXE at: dist\RossiSiteGuardMonitor.exe
pause

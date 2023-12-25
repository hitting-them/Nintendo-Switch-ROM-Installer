@echo off
pip install bs4 curl_cffi requests_html lxml

if %errorlevel% equ 0 (
    echo Installation successful.
    echo Deleting this script...
    del "%~f0"
) else (
    echo Installation failed. Please check for errors.
)

pause
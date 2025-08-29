@echo off
setlocal

set "file=%~f0"
set "dir=%file:run.bat=%"

if not exist "%dir%.venv\Scripts\activate.bat" (
    python -m venv "%dir%.venv"
)

call "%dir%.venv\Scripts\activate.bat"

python "%dir%src\" %*

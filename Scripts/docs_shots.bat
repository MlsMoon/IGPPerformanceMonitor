@echo off
:: Grab user-manual screenshots from the real window (no admin).
:: Staging: temp\docs-shots\   Publish: python -m src.selfcheck.docs_shots --publish-only
cd /d "%~dp0\.."
python -m src.selfcheck.docs_shots %*

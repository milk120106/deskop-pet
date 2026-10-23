@echo off
setlocal EnableExtensions
cd /d "%~dp0"
where py >nul 2>nul && set PY=py || set PY=python
rem Python.org security guidance for the October 2026 eMudhra/emSign CA incident.
rem Bootstrap pip from the hash-pinned official PyPI wheel before upgrading certifi.
%PY% -m pip install --no-cache-dir --force-reinstall "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
if errorlevel 1 goto :error
%PY% -m pip install --upgrade --no-cache-dir "certifi>=2026.10.19"
if errorlevel 1 goto :error
%PY% -m pip --version
%PY% -c "import certifi; print('certifi', certifi.__version__); print(certifi.where())"
echo Python TLS dependencies are updated.
exit /b 0
:error
echo Security dependency update failed. Do not run the application until it succeeds.
pause
exit /b 1

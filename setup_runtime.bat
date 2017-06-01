@echo off

set pythonEnv=cikitenv
set requirements=requirements.txt
set pythonEnvPath=%~dp0%pythonEnv%
set requirementsPath=%~dp0%requirements%

set NUL=NUL
if "%OS%" == "Windows_NT" set NUL=

if not exist %pythonEnvPath%\%NUL% (
    echo Create python virtual environment %pythonEnv%
    virtualenv %pythonEnv%
)

if exist %requirementsPath% (
    echo Install python packages to python virtual environment %pythonEnv%
    %pythonEnv%\Scripts\pip.exe install -r %requirements%
)

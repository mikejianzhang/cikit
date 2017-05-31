@echo off

set pythonEnv=cikitenv
set requirements=requirements.txt

if not exit %pythonEnv% (
    virtualenv %pythonEnv%
)

if exit %requirements (
    %pythonEnv%\bin\pip install -r %requirements%
)

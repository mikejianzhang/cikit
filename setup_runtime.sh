#!/usr/bin/env bash

pythonEnv="cikitenv"
requirements="requirements.txt"

if [ ! -d "${pythonEnv}" ]
then
    echo "Create python virtual environment!"
    virtualenv "${pythonEnv}"
fi

if [ -f "${requirements}" ]
then
    "${pythonEnv}/bin/pip" install -r "${requirements}"
fi
#!/bin/env bash

file=$(realpath "$0")
dir=${file/run\.sh/}

if ! [[ -f "${dir}.venv/bin/activate" ]]
then
    python -m venv "${dir}.venv"
fi

source "${dir}.venv/bin/activate"

python "${dir}src/" "$@"

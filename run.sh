#!/bin/sh

if [ ! -d ".tox" ]; then
    tox -e py3
fi

source .tox/py3/bin/activate

pip install -Uqr requirements.txt

python3 src/client.py

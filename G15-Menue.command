#!/bin/zsh
# Double-click to run in Terminal, where macOS can request Music/Spotify access.
cd -- "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
    print 'Bitte zuerst die Python-Umgebung wie in README.md beschrieben installieren.'
    read '?Weiter mit Eingabetaste ...'
    exit 1
fi
exec .venv/bin/python -m g15display menu "$@"

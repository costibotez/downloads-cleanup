#!/bin/bash
# Double-click to start Downloads Sorter in your browser.
cd "$(dirname "$0")" || exit 1
exec python3 app/server.py

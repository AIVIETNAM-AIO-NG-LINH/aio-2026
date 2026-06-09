#!/usr/bin/env bash
#
# Tao venv "vendor" + cai thu vien Python cho IDE (autocomplete, goi y import).
# KHONG cai mysqlclient (goi nay can MariaDB de build) — app that chay trong Docker.
#
# Cach dung:
#   ./macos-script.sh
#   source vendor/bin/activate     # de dung venv o terminal hien tai
#
set -euo pipefail

# --- 1. Kiem tra Python ----------------------------------------------------
if command -v python3.13 >/dev/null 2>&1; then
  PYTHON="python3.13"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "LOI: Khong tim thay python3 tren may." >&2
  exit 1
fi

PY_VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo ">> Dung $PYTHON (phien ban $PY_VERSION)"

# --- 2. Tao virtualenv "vendor" -------------------------------------------
if [ ! -d vendor ]; then
  echo ">> Tao virtualenv: vendor"
  "$PYTHON" -m venv vendor
fi

# --- 3. Cai thu vien (bo qua mysqlclient) ---------------------------------
echo ">> Nang cap pip & cai requirements (tru mysqlclient) ..."
vendor/bin/python -m pip install --upgrade pip
grep -v -i 'mysqlclient' requirements.txt | vendor/bin/python -m pip install --no-cache-dir -r /dev/stdin

echo ""
echo "Xong. Kich hoat venv bang lenh:"
echo "   source vendor/bin/activate"

#!/usr/bin/env bash
# Sourced by cron — loads .env then runs monitor.py
set -e
cd "/home/user/memecoin-intel"
[ -f .env ] && export $(grep -v '^#' .env | xargs)
exec "/usr/local/bin/python3" monitor.py >> "/home/user/memecoin-intel/monitor.log" 2>&1

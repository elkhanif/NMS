FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir snmpsim-lextudio

COPY snmp-data ./snmp-data
COPY fake_targets.py ./fake_targets.py

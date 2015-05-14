#!/bin/bash

sudo /bin/bash -c "source venv/bin/activate && code/engine/engine.py https://localhost:8080/api local persistent/keys/client-engine-local-key+cert.pem --no_verify --no_remove"

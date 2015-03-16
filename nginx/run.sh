#!/bin/bash

# Combine system certificates with any user certs into a single file.
# Don't freak out if there are no client certificates installed.
cp /etc/ssl/certs/ca-certificates.crt /tmp/ssl-ca-certs
cat /etc/ssl/certs/ca-certificates.crt /etc/nginx/client-*.ca.pem > /tmp/ssl-ca-certs

# Run
nginx $@

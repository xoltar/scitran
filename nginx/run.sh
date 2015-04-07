#!/bin/bash

# combine the ca-certificates bundle with out our trusted CA certificate
cat /etc/ssl/certs/ca-certificates.crt /etc/nginx/rootCA-cert.pem > /etc/nginx/ca-certificates+scitranCA.crt

# start
nginx $@

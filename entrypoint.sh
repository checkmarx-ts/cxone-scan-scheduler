#!/bin/bash

cp /etc/ssl/certs/ca-certificates.crt /opt/cxone/certs/certs.crt

export REQUESTS_CA_BUNDLE=/opt/cxone/certs/certs.crt

for cert in $(find /usr/share/ca-certificates -maxdepth 1 -name '*.crt' -print);
do
    if [[ -n "$LOG_LEVEL" && $LOG_LEVEL == "DEBUG" ]]; then
        echo Adding $cert as a trusted CA certificate...
    fi
    cat $cert >> /opt/cxone/certs/certs.crt
done

python3 "$@"

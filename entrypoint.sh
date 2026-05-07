#!/bin/bash

cat /etc/ssl/certs/ca-certificates.crt > /opt/cxone/certs.crt
export REQUESTS_CA_BUNDLE=/opt/cxone/certs.crt

for cert in $(find /usr/local/share/ca-certificates -name '*.crt' -print);
do
    if [[ -n "$LOG_LEVEL" && $LOG_LEVEL == "DEBUG" ]]; then
        echo Adding $cert as a trusted CA certificate...
    fi
    cat $cert >> /opt/cxone/certs.crt
done

python3 "$@"

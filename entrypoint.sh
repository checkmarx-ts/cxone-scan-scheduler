#!/bin/bash

update-ca-certificates
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
echo "export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt" >> /etc/environment

[ -n "$CXONE_REGION" ] && echo "export CXONE_REGION=$CXONE_REGION" >> /etc/environment
[ -n "$SINGLE_TENANT_AUTH" ] && echo "export SINGLE_TENANT_AUTH=$SINGLE_TENANT_AUTH" >> /etc/environment
[ -n "$SINGLE_TENANT_API" ] && echo "export SINGLE_TENANT_API=$SINGLE_TENANT_API" >> /etc/environment
[ -n "$LOG_LEVEL" ] && echo "export LOG_LEVEL=$LOG_LEVEL" >> /etc/environment
[ -n "$SSL_VERIFY" ] && echo "export SSL_VERIFY=$SSL_VERIFY" >> /etc/environment
[ -n "$PROXY" ] && echo "export PROXY=$PROXY" >> /etc/environment

if [ -n "$TIMEZONE" ]; then
    [ -f /usr/share/zoneinfo/$TIMEZONE ] && ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime
fi

service cron start > /dev/null 2>&1

python3 "$@"

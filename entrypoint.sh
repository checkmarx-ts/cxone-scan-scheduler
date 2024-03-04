#!/bin/bash

[ -n "$CXONE_REGION" ] && echo "export CXONE_REGION=$CXONE_REGION" >> /etc/environment
[ -n "$LOG_LEVEL" ] && echo "export LOG_LEVEL=$LOG_LEVEL" >> /etc/environment
[ -n "$SSL_VERIFY" ] && echo "export SSL_VERIFY=$SSL_VERIFY" >> /etc/environment
[ -n "$PROXY" ] && echo "export PROXY=$PROXY" >> /etc/environment

service cron start > /dev/null 2>&1

python $@

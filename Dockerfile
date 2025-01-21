FROM ubuntu:24.04
LABEL org.opencontainers.image.source="https://github.com/checkmarx-ts/cxone-scan-scheduler"
LABEL org.opencontainers.image.vendor="Checkmarx Professional Services"
LABEL org.opencontainers.image.title="Checkmarx One Scan Scheduler"
LABEL org.opencontainers.image.description="Schedules scans for projects in Checkmarx One"

USER root

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata && \
    apt-get install -y cron python3.12 python3-pip python3-debugpy bash && \
    usermod -s /bin/bash nobody && \
    mkdir -p /opt/cxone && \
    mkfifo /opt/cxone/logfifo && \
    chown nobody:root /opt/cxone/logfifo


WORKDIR /opt/cxone
COPY *.txt *.whl /opt/cxone

RUN pip install -r requirements.txt --no-cache-dir --break-system-packages && \
    apt-get remove -y perl && \
    apt-get autoremove -y && \
    apt-get clean && \
    dpkg --purge $(dpkg --get-selections | grep deinstall | cut -f1)

RUN [ -f *.whl ] && pip install --no-cache-dir --break-system-packages *.whl || :

COPY *.py entrypoint.sh *.json /opt/cxone/
COPY logic /opt/cxone/logic
COPY utils /opt/cxone/utils

RUN ln -s scheduler.py scheduler && \
    ln -s scheduler.py audit

CMD ["scheduler"]
ENTRYPOINT ["/opt/cxone/entrypoint.sh"]
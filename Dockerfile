FROM python:3.12
LABEL org.opencontainers.image.source https://github.com/checkmarx-ts/cxone-scan-scheduler
LABEL org.opencontainers.image.vendor Checkmarx Professional Services
LABEL org.opencontainers.image.title Checkmarx One Scan Scheduler
LABEL org.opencontainers.image.description Schedules scans for projects in Checkmarx One


RUN apt-get update && apt-get install -y cron && apt-get clean && \
    usermod -s /bin/bash nobody && \
    mkdir -p /opt/cxone && \
    mkfifo /opt/cxone/logfifo && \
    chown nobody:root /opt/cxone/logfifo


WORKDIR /opt/cxone
COPY *.txt /opt/cxone
RUN pip install debugpy && pip install -r requirements.txt


COPY cxone_api /opt/cxone/cxone_api
COPY logic /opt/cxone/logic
COPY utils /opt/cxone/utils
COPY *.py /opt/cxone
COPY entrypoint.sh /opt/cxone
COPY *.json /opt/cxone


RUN ln -s scheduler.py scheduler && \
    ln -s scheduler.py audit

CMD ["scheduler"]
ENTRYPOINT ["/opt/cxone/entrypoint.sh"]
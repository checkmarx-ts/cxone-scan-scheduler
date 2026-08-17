FROM ubuntu:26.04@sha256:f3d28607ddd78734bb7f71f117f3c6706c666b8b76cbff7c9ff6e5718d46ff64 AS base
LABEL org.opencontainers.image.source="https://github.com/checkmarx-ts/cxone-scan-scheduler"
LABEL org.opencontainers.image.vendor="Checkmarx Professional Services"
LABEL org.opencontainers.image.title="Checkmarx One Scan Scheduler"
LABEL org.opencontainers.image.description="Schedules scans for projects in Checkmarx One"

USER root

RUN export DEBIAN_FRONTEND=noninteractive && \
    echo 'Acquire::EnableSrvRecords "false";' >> /etc/apt/apt.conf.d/99-nosrv && \
    apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends tzdata=2026a-3ubuntu1 python3=3.14.3-0ubuntu2 python3-pip=25.1.1+dfsg-1ubuntu2 && \
    apt-get remove -y perl && \
    apt-get autoremove -y && \
    apt-get clean && \
    groupadd -U nobody scheduler && \
    mkdir -p /opt/cxone/certs && \
    chown root:scheduler /opt/cxone/certs && \
    chmod 770 /opt/cxone/certs


COPY requirements.txt /opt/cxone/
COPY *.py entrypoint.sh *.json /opt/cxone/
COPY logic /opt/cxone/logic
COPY utils /opt/cxone/utils
COPY scan /opt/cxone/scan

WORKDIR /opt/cxone
RUN --mount=type=secret,id=PACKAGE_INDEX \
    pip install -r requirements.txt --no-cache-dir --break-system-packages $([ -f "/run/secrets/PACKAGE_INDEX" ] && printf -- "--index-url $(cat /run/secrets/PACKAGE_INDEX)" ) && \
    rm requirements.txt && \
    ln -s scheduler.py scheduler && \
    ln -s scheduler.py audit

CMD ["scheduler"]
ENTRYPOINT ["/opt/cxone/entrypoint.sh"]

FROM base AS debug
COPY requirements.txt *.whl /opt/cxone/
RUN --mount=type=secret,id=PACKAGE_INDEX \
    apt-get install -y python3-debugpy=1.8.19+ds-1ubuntu3 python3-pytest=9.0.2-4
RUN --mount=type=secret,id=PACKAGE_INDEX \
    apt-get install -y python3-debugpy=1.8.19+ds-1ubuntu3 python3-pytest=9.0.2-4 && \
    [ -f *.whl ] && pip install --no-cache-dir --break-system-packages *.whl $([ -f "/run/secrets/PACKAGE_INDEX" ] && printf -- "--index-url $(cat /run/secrets/PACKAGE_INDEX)" ) || :

FROM base AS release
USER nobody


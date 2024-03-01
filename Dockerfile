FROM python:3.12

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


# ENTRYPOINT ["python", "-Xfrozen_modules=off", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client"]
CMD ["scheduler.py"]
ENTRYPOINT ["/opt/cxone/entrypoint.sh"]
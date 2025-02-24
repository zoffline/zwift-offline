FROM python:3.12-slim
LABEL maintainer="zoffline <zoffline@tutanota.com>"

WORKDIR /usr/src/app/zwift-offline
COPY . .

RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt
RUN pip install --no-cache-dir --root-user-action=ignore garth

RUN chmod 777 storage

EXPOSE 443 80 3024/udp 3025 53/udp

VOLUME /usr/src/app/zwift-offline/storage

CMD [ "python", "standalone.py" ]

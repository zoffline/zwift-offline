FROM python:3.12-alpine AS builder

WORKDIR /usr/src/app

RUN apk add --no-cache git gcc g++ musl-dev libffi-dev openssl-dev file make

RUN mkdir -p ./zwift-offline
COPY ./ ./zwift-offline

RUN pip install --user --requirement ./zwift-offline/requirements.txt
RUN pip install --user garth

FROM python:3.12-alpine
LABEL maintainer="zoffline <zoffline@tutanota.com>"

WORKDIR /usr/src/app

COPY --from=builder /root/.local/ /root/.local/
ENV PATH=/root/.local/bin:$PATH

COPY --from=builder /usr/src/app/zwift-offline/ zwift-offline/
RUN chmod 777 zwift-offline/storage

EXPOSE 443 80 3024/udp 3025 53/udp

VOLUME /usr/src/app/zwift-offline/storage

CMD [ "python", "zwift-offline/standalone.py" ]

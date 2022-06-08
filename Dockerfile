FROM python:3-alpine as builder

WORKDIR /usr/src/app

RUN apk add --no-cache git gcc g++ musl-dev libffi-dev openssl-dev file make
RUN pip install --user flask flask_sqlalchemy flask-login pyjwt gevent protobuf protobuf3_to_dict stravalib garmin-uploader requests dnspython

RUN git clone --depth 1 https://github.com/zoffline/zwift-offline

FROM python:3-alpine
MAINTAINER zoffline <zoffline@tutanota.com>

WORKDIR /usr/src/app

COPY --from=builder /root/.local/ /root/.local/
ENV PATH=/root/.local/bin:$PATH

COPY --from=builder /usr/src/app/zwift-offline/ zwift-offline/
RUN chmod 777 zwift-offline/storage

EXPOSE 443 80 3022/udp 3023 53/udp

VOLUME /usr/src/app/zwift-offline/storage

CMD [ "python", "zwift-offline/standalone.py" ]

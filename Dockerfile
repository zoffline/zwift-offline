FROM python:3-alpine
MAINTAINER zoffline <zoffline@tutanota.com>

WORKDIR /usr/src/app

RUN apk add --no-cache git
RUN pip install flask flask_sqlalchemy flask-login pyjwt protobuf protobuf3_to_dict stravalib

RUN git clone --depth 1 https://github.com/zoffline/zwift-offline
RUN chmod 777 zwift-offline/storage

EXPOSE 443 80 3022/udp 3023

VOLUME /usr/src/app/zwift-offline/storage

CMD [ "python", "zwift-offline/standalone.py" ]

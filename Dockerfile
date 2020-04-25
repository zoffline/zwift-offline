FROM python:2-alpine
MAINTAINER zoffline <zoffline@tutanota.com>

WORKDIR /usr/src/app

RUN apk add --no-cache git
RUN pip install flask protobuf protobuf_to_dict stravalib garmin-uploader

RUN git clone --depth 1 https://github.com/zoffline/zwift-offline
RUN chmod 777 zwift-offline/storage

EXPOSE 443 80

VOLUME /usr/src/app/zwift-offline/storage

CMD [ "python", "zwift-offline/standalone.py" ]

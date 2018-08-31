FROM httpd:2.4
MAINTAINER zoffline <zoffline@tutanota.com>

RUN apt-get update && apt-get install -y python-dev python-flask libapache2-mod-wsgi python-pip protobuf-compiler git
RUN pip install --upgrade six
RUN pip install protobuf protobuf_to_dict stravalib
RUN ln -s /usr/lib/apache2/modules/mod_wsgi.so /usr/local/apache2/modules/

RUN git clone --depth 1 https://github.com/zoffline/zoffline /usr/local/apache2/htdocs/zwift-offline
RUN cd /usr/local/apache2/htdocs/zwift-offline/protobuf && make
RUN chown -R www-data.www-data /usr/local/apache2/htdocs/zwift-offline
RUN chmod 777 /usr/local/apache2/htdocs/zwift-offline/storage
COPY apache/docker-httpd.conf /usr/local/apache2/conf/httpd.conf

EXPOSE 443 80

VOLUME /usr/local/apache2/htdocs/zwift-offline/storage

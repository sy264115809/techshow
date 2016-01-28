FROM ubuntu:14.04

MAINTAINER Shaoyu <shaoyu@qiniu.com>

# install python and pip
RUN sed -i 's/http:\/\/archive\.ubuntu\.com\/ubuntu\//http:\/\/mirrors\.163\.com\/ubuntu\//g' /etc/apt/sources.list
RUN apt-get update && apt-get -y install \
    python-pip \
    python-dev \
    libmysqld-dev \
    supervisor

# make project directory
RUN mkdir -p /home/www/techshow
WORKDIR /home/www/techshow

# copy requirements file and install dependancy
COPY requirements.txt .
RUN pip install -r requirements.txt

# app relevant
COPY app app
COPY manage.py .
COPY celery_tasks.py .

# app config and env
COPY config.py .
COPY .env .
COPY gunicorn_config.py .

# migration
COPY migrations migrations

# supervisor
COPY supervisor.conf /etc/supervisor/conf.d/techshow.conf

# expose
EXPOSE 8000

# cmd
CMD ["/usr/bin/supervisord", "-n"]
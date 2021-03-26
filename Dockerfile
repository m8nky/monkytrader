FROM python:3.8-alpine

WORKDIR /usr/src/app

RUN addgroup -g 1003 -S app \
    && adduser -u 1003 -S app -G app \
    && mkdir -p /var/lib/msapp \
    && chown app:app /var/lib/msapp \
    && apk add gcc g++ musl-dev libffi-dev openssl-dev rust cargo

RUN pip install --upgrade pip \
    && pip install --no-cache-dir gunicorn==19.9.0 falcon==2.0.0 requests simplejson ulid pytz apscheduler nose python-binance redis

COPY app/ .

USER app

EXPOSE 9501

CMD ["gunicorn", "-c", "python:msapp.config.gunicorn", "msapp.run:app"]

FROM python:3.12-alpine3.22

RUN adduser --disabled-password appuser

COPY requirements.txt /temp/requirements.txt
COPY database / database

WORKDIR /database
EXPOSE 8000

RUN apk add postgresql-client build-base postgresql-dev
RUN pip install -r /temp/requirements.txt

USER appuser
FROM docker.io/python:slim

WORKDIR /usr/src/app
COPY requirements.txt /tmp/
ENV DEBIAN_FRONTEND=noninteractive
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY --exclude=requirements.txt .

EXPOSE 8080/tcp
ENV CLOUD_INIT_HOST="0.0.0.0"
ENV CLOUD_INIT_PORT="8080"
ENTRYPOINT [ "python", "./app.py" ]
CMD [ "server" ]

FROM docker.io/python:slim

WORKDIR /usr/src/app
COPY requirements.txt ./
ENV DEBIAN_FRONTEND=noninteractive
RUN pip install --no-cache-dir -r requirements.txt && apt update && apt install -y graphviz && rm -rf /var/lib/apt/lists/*

COPY . .

#trigger

EXPOSE 8080/tcp
ENV CLOUD_INIT_HOST="0.0.0.0"
ENV CLOUD_INIT_PORT="8080"
CMD [ "python", "./app.py" ]

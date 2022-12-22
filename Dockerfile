FROM python:3.9-slim

LABEL maintainer="Max Mecklin <max@meckl.in>"

COPY . /app

#COPY docker-entrypoint.sh /docker-entrypoint.sh
#RUN ["chmod", "+x", "/docker-entrypoint.sh"]

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*

RUN pip3.9 install -r requirements.txt
RUN pip3.9 install git+https://github.com/Natsku123/pygw2

ENV PYTHONPATH "${PYTHONPATH}:/app"

#ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python3.9", "main.py"]

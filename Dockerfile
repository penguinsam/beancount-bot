FROM python:3.10-slim AS bot

ENV PYTHONFAULTHANDLER=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONHASHSEED=random
ENV PYTHONDONTWRITEBYTECODE 1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV PIP_DEFAULT_TIMEOUT=100

RUN apt-get update
RUN apt-get install -y python3 python3-pip python3-dev build-essential

RUN mkdir -p /codebase
ADD . /codebase
WORKDIR /codebase
RUN pip3 install -r requirements.txt

#CMD python3 /codebase/beanbot.py;
ENTRYPOINT ["python3", "/codebase/beanbot.py"]

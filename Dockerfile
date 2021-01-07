FROM python:3.7

WORKDIR /usr/src/energymeter

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update
RUN apt-get install -y ca-certificates curl gcc make python-dev
RUN pip3 install RPi.GPIO

COPY energymeter.py ./

RUN touch .env
RUN echo $"is_docker=true" > .env

CMD ["python", "energymeter.py"]
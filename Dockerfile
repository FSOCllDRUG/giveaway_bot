FROM python:3.13

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

ENV PYTHONUNBUFFERED=1

CMD ["python", "run.py"]
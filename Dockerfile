FROM python:3.8-slim

WORKDIR /app
COPY requirements.txt /app
RUN pip install -r requirements.txt \
    && pip cache purge

COPY . /app

CMD ["python", "Sharoho.py"]

FROM docker.io/library/python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sdf.py server.py ./

EXPOSE 5000

CMD ["python", "server.py"]

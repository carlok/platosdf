FROM docker.io/library/python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir numpy trimesh scipy scikit-image pytest
COPY evolver.py fitness.py mutate.py grammar_name.py config.json ./
CMD ["python", "evolver.py"]

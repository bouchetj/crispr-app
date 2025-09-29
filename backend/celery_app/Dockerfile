FROM mambaorg/micromamba:1.5.8

ENV MAMBA_DOCKERFILE_ACTIVATE=1
ENV PYTHONPATH=/app:/app/backend
WORKDIR /app

COPY environment.yml /tmp/environment.yml
RUN micromamba create -y -n celery -f /tmp/environment.yml && micromamba clean -a -y

COPY requirements.txt /tmp/requirements.txt
RUN micromamba run -n celery python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY .. /app

CMD ["micromamba", "run", "-n", "celery", "celery", "-A", "backend.celery_app.celery_app.celery_app", "worker", "--loglevel=info"]

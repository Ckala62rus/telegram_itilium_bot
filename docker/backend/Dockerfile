FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    TZ=Europe/Moscow

WORKDIR /src

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY ./src/pyproject.toml ./src/poetry.lock /src/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir poetry==1.8.3 poetry-plugin-export \
    && poetry export --without-hashes -f requirements.txt -o /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -rf /root/.cache/pip

COPY ./src /src

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

CMD ["python", "app.py"]

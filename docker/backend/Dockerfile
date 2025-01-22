FROM python:3.12-alpine

WORKDIR /src

COPY ./src/pyproject.toml \
    ./src/poetry.lock /src/

RUN apk --update add mc curl curl bash nano

RUN apk --update add \
    && pip install poetry \
    && pip install poetry-plugin-export \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && pip install poetry \
    && poetry export --without-hashes -f requirements.txt --output requirements.txt \
    && pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple \
    && pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt

ENV TZ = Europa/Moscow

CMD ["timedatectl", "set-timezone", "Europe/Moscow"]

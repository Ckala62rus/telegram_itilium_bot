FROM python:3.12-alpine as builder

WORKDIR /src

COPY ./src/pyproject.toml \
    ./src/poetry.lock /src/

COPY ./src .


FROM python:3.12-alpine

WORKDIR /src

COPY --from=builder /src /src

RUN apk --update add mc curl curl bash nano

#RUN pip install poetry && pip install poetry-plugin-export

#RUN apk --update add \
##    && pip install poetry \
##    && pip install poetry-plugin-export \
#    && curl -sSL https://install.python-poetry.org | python3 - \
#    && pip install poetry \
#    && poetry export --without-hashes -f requirements.txt --output requirements.txt \
#    && pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple \
#    && pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple \
#    && rm -rf /var/lib/apt/lists/* \
#    && rm -rf /var/cache/apt

#RUN pip install --no-index --find-links /vendor -r requirements_dev.txt
#RUN pip install ./src/vendor/*.whl
RUN pip install -r requirements.txt --no-index -f vendor

ENV TZ = Europa/Moscow
CMD ["timedatectl", "set-timezone", "Europe/Moscow"]

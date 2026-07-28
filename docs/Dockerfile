# Собирает Jupyter Book (docs/) в статический HTML и раздаёт его.
# Контекст сборки — корень репозитория (как у api/Dockerfile, dash_app/Dockerfile).

FROM python:3.12-slim AS build

WORKDIR /app

COPY requirements-docs.txt .
RUN pip install --no-cache-dir -r requirements-docs.txt

COPY docs/ ./docs/
WORKDIR /app/docs
# jupyter-book (mystmd) ставит собственный изолированный Node через nodeenv —
# системный Node/npm не нужен.
RUN jupyter-book build --html

FROM python:3.12-slim
COPY --from=build /app/docs/_build/html /site
EXPOSE 8080
# $PORT подставляет Railway; sh -c обязателен для expansion переменной
# (тот же приём, что dash_app/Dockerfile).
CMD ["sh", "-c", "python -m http.server ${PORT:-8080} --directory /site"]

# Собирает Jupyter Book (docs/) в статический HTML и раздаёт его.
# Контекст сборки — корень репозитория (как у api/Dockerfile, dash_app/Dockerfile).

FROM python:3.12-slim AS build

WORKDIR /app

# jupyter-book (mystmd) требует Node >= 18. nodeenv умеет поставить свой
# изолированный Node сам, но в неинтерактивной сборке зависает на вопросе
# "Install Node.js? (y/N)" (нет stdin) — поэтому ставим системный Node явно,
# nodeenv находит его и ничего сам не устанавливает.
# procps (ps) нужен по той же причине: после статического экспорта сайта
# mystmd останавливает свой временный dev-сервер через `ps`, которого нет
# в минимальном python:3.12-slim — без него сборка падает уже ПОСЛЕ того,
# как сайт полностью собран (Error: spawn ps ENOENT).
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docs.txt .
RUN pip install --no-cache-dir -r requirements-docs.txt

COPY docs/ ./docs/
WORKDIR /app/docs
RUN jupyter-book build --html

FROM python:3.12-slim
COPY --from=build /app/docs/_build/html /site
EXPOSE 8080
# $PORT подставляет Railway; sh -c обязателен для expansion переменной
# (тот же приём, что dash_app/Dockerfile).
CMD ["sh", "-c", "python -m http.server ${PORT:-8080} --directory /site"]

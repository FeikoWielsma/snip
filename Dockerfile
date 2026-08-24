# A deliberately naive, single-stage image.
#
# It works, and it is roughly a gigabyte, because it ships the full CPython
# image, the uv binary, the build toolchain and the entire test suite into
# production. Exercise 6 turns this into a multi-stage build and measures the
# difference; leaving it naive here is the point.

FROM python:3.12

WORKDIR /app

RUN pip install uv

COPY . .

RUN uv sync --frozen

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

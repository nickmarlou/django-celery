FROM python:3.7-alpine

ENV \
    # Avoiding situations where the application crashes and logs "stuck" in a buffer
    # https://docs.python.org/3.3/using/cmdline.html#cmdoption-u
    PYTHONUNBUFFERED=1 \
    # Disable pip cache to make docker image smaller
    PIP_NO_CACHE_DIR=1 \
    # Disable pip version check
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps
RUN apk update \
    && apk --no-cache add \
    git \
    bash \
    build-base \
    python3-dev \
    # Pillow dependencies
    # https://github.com/python-pillow/docker-images/blob/master/alpine/Dockerfile
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    tk-dev \
    tcl-dev \
    harfbuzz-dev \
    fribidi-dev \
    # Translations dependencies
    gettext \
    # PostgreSQL dependencies
    postgresql-dev \
    postgresql-client \
    # `lxml` dependencies
    g++ \
    libxml2 \
    libxml2-dev \
    libxslt-dev

WORKDIR /app

# Install requirements
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Add code to container
ADD ./ /app/

# Create a group and user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN chown -R appuser /app

# Tell docker that all future commands should run as the appuser user
USER appuser
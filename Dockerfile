FROM python:3.6-stretch

ENV \
    # Avoiding situations where the application crashes and logs "stuck" in a buffer
    # https://docs.python.org/3.3/using/cmdline.html#cmdoption-u
    PYTHONUNBUFFERED=1 \
    # Disable pip cache to make docker image smaller
    PIP_NO_CACHE_DIR=1 \
    # Disable pip version check
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install requirements
COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Add code to container
ADD ./ /app/

# Create group and user
RUN addgroup --system appgroup
RUN adduser --system --ingroup appgroup appuser

# Set owner and permissions
RUN chown -R appuser /app

# Tell docker that all future commands should run as the appuser user
USER appuser
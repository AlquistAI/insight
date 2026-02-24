FROM python:3.11-slim-bookworm AS builder

WORKDIR /root

# Install core Python packages and pipenv
RUN pip install --disable-pip-version-check --no-cache-dir pipenv setuptools wheel

# Install Python dependencies
COPY common common
COPY ragnarok/Pipfile ragnarok/Pipfile.lock ragnarok/
RUN cd ragnarok && pipenv install --deploy --system

FROM python:3.11-slim-bookworm AS runtime

# Copy Python dependencies from builder
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Install additional runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Create a new user and group (to not run docker as a root user)
ENV USER=app
ENV USER_HOME=/home/$USER
RUN groupadd -g 999 $USER \
    && useradd -r -u 999 -g $USER $USER \
    && mkdir -p $USER_HOME \
    && chown $USER:$USER -R $USER_HOME

USER $USER
WORKDIR $USER_HOME

# Make the app available to be imported globally
ENV PYTHONPATH=$USER_HOME

# Copy runtime files
COPY --chown=999:999 ragnarok ./
RUN chmod +x start.sh

CMD ["./start.sh"]
EXPOSE 9696

# Based off WolfiOS
FROM cgr.dev/chainguard/wolfi-base

# Set Python version
ARG version=3.12

RUN apk update && apk add --no-cache \
    python-${version} \
    py${version}-pip \
    py${version}-setuptools \
    ca-certificates

WORKDIR /app

COPY main.py .
COPY requirements.txt .
COPY platforms ./platforms
ADD https://truststore.pki.rds.amazonaws.com/us-west-2/us-west-2-bundle.pem ./aws-ssl-certs/

# Install requirements
# Disable caching, to keep Docker image lean
RUN pip install --no-cache-dir -r requirements.txt

# Run as non-root user
# uid and gid are 65532
RUN chown -R nonroot:nonroot /app/

USER nonroot

CMD [ "python", "/app/main.py" ]

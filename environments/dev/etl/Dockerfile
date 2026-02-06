# syntax=docker/dockerfile:1

# Stage 1: Get PySpark and Spark jars from official image
FROM apache/spark:4.1.1-python3 AS spark-base

# Stage 2: Build the final image
FROM python:3.12-slim

# Install Java (required for PySpark)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    curl

# Set Java environment (portable across arm64 and amd64)
RUN ln -s /usr/lib/jvm/java-21-openjdk-* /usr/lib/jvm/java-21-openjdk
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Copy Spark jars, bin, and PySpark from official image (avoids 300+ second pip install)
COPY --from=spark-base /opt/spark/jars /opt/spark/jars
COPY --from=spark-base /opt/spark/bin /opt/spark/bin
COPY --from=spark-base /opt/spark/python/pyspark /usr/local/lib/python3.12/site-packages/pyspark
COPY --from=spark-base /opt/spark/python/lib /opt/spark/python/lib

# Set Spark environment
ENV SPARK_HOME=/opt/spark
ENV PYTHONPATH="${PYTHONPATH}:/opt/spark/python/lib/py4j-0.10.9.9-src.zip"

# Set working directory
WORKDIR /app

# Install remaining Python dependencies (small packages, fast install)
COPY pyproject.toml .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 3 --timeout 120 \
    delta-spark==4.0.1 psycopg2-binary>=2.9.9 requests python-dateutil google-cloud-storage

# Download GCS connector for Spark (pinned version for reproducibility)
RUN curl -L --retry 3 --retry-delay 5 -o /opt/spark/jars/gcs-connector-hadoop3-2.2.25.jar \
    https://storage.googleapis.com/hadoop-lib/gcs/gcs-connector-hadoop3-2.2.25.jar

# Copy project files
COPY environments/dev/ ./environments/dev/

# Install package in editable mode (fast, deps already installed)
RUN pip install --no-cache-dir --no-deps -e .

# Set Python path
ENV PYTHONPATH=/app:/app/environments/dev

# Keep container running for development
CMD ["tail", "-f", "/dev/null"]

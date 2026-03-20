# JackpotChain Node Dockerfile
FROM python:3.12-slim

LABEL maintainer="JackpotChain Team"
LABEL version="1.0"
LABEL description="JackpotChain - UTXO-based blockchain with on-chain lottery"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY jackpotchain/ ./jackpotchain/

# Create data directory
RUN mkdir -p /app/data /app/wallet

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default ports
# P2P: 9777, RPC: 9776
EXPOSE 9777 9776

# Volume for persistent data
VOLUME ["/app/data", "/app/wallet"]

# Default command (node only, no mining)
# Override with --mine --address for mining node
ENTRYPOINT ["python", "-m", "jackpotchain.cli.main"]
CMD ["node", "--port", "9777", "--rpc-port", "9776", "--data-dir", "/app/data"]

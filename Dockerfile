# Start from a recent Node.js image with Debian Bookworm for best compatibility
FROM node:20-bookworm

# Install Python, venv, and system dependencies for Playwright and Chrome
RUN apt-get update && \
    apt-get install -y \
    python3 python3-venv python3-pip \
    wget curl gnupg ca-certificates \
    fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libnspr4 \
    libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 \
    xdg-utils lsb-release libu2f-udev libvulkan1 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*


# RUN apt-get install -y wget
# RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
# RUN apt-get install -y ./google-chrome-stable_current_amd64.deb

# Install Playwright and its browsers (includes Chrome/Chromium)
RUN npm install -g playwright && \
    npx playwright install --with-deps

# Install Deno (latest stable)
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh && \
    ln -s /usr/local/bin/deno /usr/bin/deno

# Set up working directory
WORKDIR /app

# Copy backend requirements
COPY backend/requirements.txt ./backend/

# Create Python virtual environment and install uv + requirements
RUN python3 -m venv .venv && \
    . .venv/bin/activate && \
    pip install --upgrade pip && \
    pip install uv && \
    uv pip install -r backend/requirements.txt

# Copy backend and frontend code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Install frontend dependencies
WORKDIR /app/frontend
RUN npm install

# Return to root directory
WORKDIR /app
RUN npm install @playwright/mcp
RUN npx playwright install firefox


# Copy and set permissions for start script
COPY start.sh .
RUN chmod +x start.sh

# Expose ports
EXPOSE 8000
EXPOSE 3000

# Start the application
CMD ["./start.sh"]

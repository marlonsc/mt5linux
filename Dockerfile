FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV WINEDEBUG=-all
ENV WINEPREFIX=/root/.wine
ENV PYTHONUNBUFFERED=1

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    software-properties-common \
    gnupg2 \
    winbind \
    xvfb \
    python3 \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Wine
RUN dpkg --add-architecture i386 && \
    mkdir -pm755 /etc/apt/keyrings && \
    wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key && \
    wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources && \
    apt-get update && \
    apt-get install -y --install-recommends winehq-stable && \
    rm -rf /var/lib/apt/lists/*

# Install Python for Windows
RUN mkdir -p /tmp/python_install && \
    cd /tmp/python_install && \
    wget https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe && \
    xvfb-run wine python-3.9.13-amd64.exe /quiet InstallAllUsers=1 PrependPath=1 && \
    rm -rf /tmp/python_install

# Install MetaTrader5 Python package on Windows Python
RUN xvfb-run wine cmd /c "C:\\Python39\\python.exe -m pip install --upgrade pip" && \
    xvfb-run wine cmd /c "C:\\Python39\\python.exe -m pip install MetaTrader5"

# Install mt5linux on Windows Python
COPY . /app
WORKDIR /app

RUN pip3 install -e . && \
    xvfb-run wine cmd /c "C:\\Python39\\python.exe -m pip install -e ."

# Expose the default port
EXPOSE 18812

# Start the RPyC server
CMD ["xvfb-run", "wine", "C:\\Python39\\python.exe", "-m", "mt5linux", "C:\\Python39\\python.exe", "--host", "0.0.0.0", "--port", "18812"]
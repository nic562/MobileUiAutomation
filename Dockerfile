FROM python:latest
COPY sources /data
RUN ls /data \
    && mv /data/debian-sources.list /etc/apt/sources.list \
    && mkdir /root/.pip && mv /data/pip.conf /root/.pip/pip.conf \
    && apt update \
    && apt -f install \
    && apt install libusb-dev -y \
    && apt install libusb-1.0-0-dev -y \
    && apt policy libx11-xcb1 \
    && apt autoremove \
    && apt install libx11-xcb1 -y \
    && apt install libgl1-mesa-glx -y \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y \
    && /bin/bash -c "source $HOME/.cargo/env" \
    && pip install -U pip \
    && pip install git+https://github.91chi.fun/https://github.com/nic562/MobileUiAutomation.git@cn --ignore-installed

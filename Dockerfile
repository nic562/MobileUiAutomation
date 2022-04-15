FROM python:3.9
COPY sources /data
RUN ls /data \
    && mv /data/debian-sources.list /etc/apt/sources.list \
    && mkdir /root/.pip && mv /data/pip.conf /root/.pip/pip.conf \
    && apt update \
    && apt -f install \
    && pip install -U pip \
    && cd /tmp && wget https://pypi.tuna.tsinghua.edu.cn/packages/c3/8d/2ae53d96a92a66b8daa3dfb2dd6cf4bfcb8e3d4148bdd713c8fc7de83141/numpy-1.19.3-cp39-cp39-manylinux2010_x86_64.whl \
    && pip install ./numpy-1.19.3-cp39-cp39-manylinux2010_x86_64.whl \
    && apt install cmake -y \
    && apt install libusb-dev -y \
    && apt install libusb-1.0-0-dev -y \
    && apt install libx11-xcb1 -y \
    && apt autoremove -y \
    && apt install libgl1-mesa-glx -y \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y \
    && /bin/bash -c "source $HOME/.cargo/env" \
    && pip install git+https://github.91chi.fun/https://github.com/nic562/MobileUiAutomation.git@cn --ignore-installed \
    && apt install adb -y

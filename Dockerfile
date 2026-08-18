# ========================================
# Base: ROS Melodic Desktop-Full (Ubuntu 18.04)
# ========================================
FROM osrf/ros:melodic-desktop-full
SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# ========================================
# Dependências Essenciais para SLAM
# ========================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    python-catkin-tools \
    python-rosdep \
    python-vcstool \
    python-pip \
    python3 \
    python3-pip \
    python3-dev \
    libpcl-dev \
    libgeographiclib-dev \
    ros-melodic-pcl-ros \
    ros-melodic-pcl-conversions \
    ros-melodic-velodyne \
    && rm -rf /var/lib/apt/lists/*

RUN rosdep update || true

# ========================================
# Ferramentas Python para Benchmark (EVO, Optuna)
# Usando pip3 pois essas libs exigem Python 3
# ========================================
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

RUN pip3 install --no-cache-dir \
    optuna \
    cmaes \
    ruamel.yaml \
    evo \
    pandas

# --- LIVOX SDK1 (compatível com Ubuntu 18.04) ---
RUN git clone https://github.com/Livox-SDK/Livox-SDK.git /tmp/Livox-SDK && \
    cd /tmp/Livox-SDK && \
    mkdir -p build && cd build && \
    cmake .. && make -j && make install && \
    rm -rf /tmp/Livox-SDK

RUN echo 'alias build_slam="catkin_make"' >> /root/.bashrc

# ========================================
# Ferramentas de avaliação (evo) — Python 2, para compatibilidade com rosbag/tf2_py
# ========================================
RUN python2 -m pip install --no-cache-dir evo --user

# Dependências do módulo rosbag quando importado a partir de ambientes Python 3
RUN pip3 install --no-cache-dir \
    pycryptodomex \
    python-gnupg \
    rospkg \
    catkin_pkg \
    defusedxml \
    pyyaml \
    netifaces \
    empy

# Suporte gráfico do evo_ape (matplotlib + Tkinter) e utilitários de terminal
RUN apt-get update && apt-get install -y --no-install-recommends \
    python-tk \
    nano \
    vim \
    && rm -rf /var/lib/apt/lists/*
    
# ========================================
# GTSAM (dependência do LeGO-LOAM)
# ========================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-all-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q -O /tmp/gtsam.zip https://github.com/borglab/gtsam/archive/4.0.0-alpha2.zip && \
    cd /tmp && unzip -q gtsam.zip && \
    cd gtsam-4.0.0-alpha2 && mkdir build && cd build && \
    cmake .. && make -j2 && make install && \
    rm -rf /tmp/gtsam.zip /tmp/gtsam-4.0.0-alpha2 && \
    ldconfig
# ========================================
# Workspace (slam_ws)
# ========================================
ENV WORKSPACE=/root/slam_ws
RUN mkdir -p $WORKSPACE/src

RUN echo "source /opt/ros/melodic/setup.bash" >> /root/.bashrc && \
    echo "if [ -f ${WORKSPACE}/devel/setup.bash ]; then source ${WORKSPACE}/devel/setup.bash; fi" >> /root/.bashrc

WORKDIR $WORKSPACE
CMD ["bash"]

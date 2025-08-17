#!/bin/bash
set -e
echo "INFO: Memulai instalasi paket sistem..."
apt-get update -y
apt-get install -y ffmpeg
echo "INFO: Instalasi FFmpeg selesai."

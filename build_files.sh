#!/bin/bash
# Script akan otomatis berhenti jika ada error
set -e

echo "INFO: Memulai instalasi paket sistem..."
# Update daftar paket dan instal FFmpeg
apt-get update -y
apt-get install -y ffmpeg
echo "INFO: Instalasi FFmpeg selesai."

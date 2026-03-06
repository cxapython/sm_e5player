#!/bin/bash
# SM Arrow Player 启动脚本
# 使用arm64架构运行PyQt6版本

cd "$(dirname "$0")"
arch -arm64 python3.11 main.py

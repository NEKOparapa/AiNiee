#!/bin/bash
set -e

# --- 路径动态识别 ---
# 获取脚本当前所在的绝对路径（即母文件夹 AiNiee 的路径）
PROJECT_DIR=$(cd "$(dirname "$0")"; pwd)
APP_NAME="AiNiee"
DIST_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"

echo "🚀 开始自动化打包 $APP_NAME (官方纯净版)..."

cd "$PROJECT_DIR"

echo "🧹 [1/3] 正在清理旧的编译缓存..."
rm -rf build dist

echo "📦 [2/3] 正在执行 PyInstaller 打包..."
python3 -m PyInstaller "$PROJECT_DIR/AiNiee.spec"

echo "🔐 [3/3] 正在修复 macOS 架构的文件执行权限..."
chmod -R 755 "$APP_BUNDLE"

echo "✅ 打包完成！软件位置: $APP_BUNDLE"
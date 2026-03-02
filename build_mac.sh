#!/bin/bash
set -e

# --- 路径动态识别 ---
PROJECT_DIR=$(cd "$(dirname "$0")"; pwd)
APP_NAME="AiNiee"
DIST_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"

echo "🚀 开始自动化打包 $APP_NAME (官方纯净版)..."

cd "$PROJECT_DIR"

echo "🧹 [1/4] 正在清理旧的编译缓存..."
rm -rf build dist
mkdir -p "$PROJECT_DIR/build/$APP_NAME"

echo "📦 [2/4] 正在执行 PyInstaller 打包..."
python3 -m PyInstaller "$PROJECT_DIR/AiNiee.spec"

echo "🩹 [3/4] [强干预] 正在物理注入 PyInstaller 漏掉的静态资源..."
# 建立目标内脏目录
mkdir -p "$APP_BUNDLE/Contents/MacOS/Resource"

# 强制物理拷贝！无视 PyInstaller 的漏包机制，将本地化、版本和模型完整复制进 App
cp -a "$PROJECT_DIR/Resource/." "$APP_BUNDLE/Contents/MacOS/Resource/"

echo "🔐 [4/4] 正在修复 macOS 架构的文件执行权限..."
chmod -R 755 "$APP_BUNDLE"

echo "✅ 打包彻底完成！软件位置: $APP_BUNDLE"
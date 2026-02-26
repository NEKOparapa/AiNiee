#!/bin/bash

# 设置遇到错误立即停止
set -e

# --- 路径动态识别 (核心修改) ---
# 获取脚本当前所在的绝对路径（即母文件夹 AiNiee 的路径）
PROJECT_DIR=$(cd "$(dirname "$0")"; pwd)
APP_NAME="AiNiee"
DIST_DIR="$PROJECT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_MACOS_DIR="$APP_BUNDLE/Contents/MacOS"

echo "🚀 开始自动化打包 $APP_NAME (M4 芯片相对路径优化版)..."
echo "📍 当前母文件夹: $PROJECT_DIR"

# 1. 进入项目目录
cd "$PROJECT_DIR"

# 2. 清理旧的打包缓存
echo "🧹 [1/4] 正在清理旧的编译文件..."
rm -rf build dist

# 3. 执行 PyInstaller 打包
# 使用 python3 -m PyInstaller 确保调用的是 Python 3.12 环境
echo "📦 [2/4] 正在执行 PyInstaller，请耐心等待..."
python3 -m PyInstaller "$PROJECT_DIR/AiNiee.spec"

# 4. 暴力物理补齐资源文件 (使用动态识别的路径)
echo "📂 [3/4] 正在强制复制资源文件夹到 .app 内部..."
# 确保目标文件夹存在
mkdir -p "$APP_MACOS_DIR"

cp -R "$PROJECT_DIR/Resource" "$APP_MACOS_DIR/"
cp -R "$PROJECT_DIR/ModuleFolders" "$APP_MACOS_DIR/"
cp -R "$PROJECT_DIR/PluginScripts" "$APP_MACOS_DIR/"

# 5. 修复 M4 芯片的系统权限
echo "🔐 [4/4] 正在修复 M4 架构的文件执行权限..."
chmod -R 755 "$APP_BUNDLE"

echo "====================================="
echo "✅ 打包与修复全部完成！"
echo "🎉 独立软件位置: $APP_BUNDLE"
echo "====================================="
echo "👉 测试运行请执行："
echo "\"$APP_MACOS_DIR/$APP_NAME\""

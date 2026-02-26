#!/bin/bash

# 设置遇到错误立即停止
set -e

# 定义路径变量
PROJECT_DIR="/Users/zhuhaogang/Desktop/AiNiee"
APP_MACOS_DIR="$PROJECT_DIR/dist/AiNiee.app/Contents/MacOS"

echo "🚀 开始自动化打包 AiNiee (针对 M4 芯片与 Python 版本兼容优化)..."

# 1. 进入项目目录
cd "$PROJECT_DIR"

# 2. 清理旧的打包缓存
echo "🧹 [1/4] 正在清理旧的编译文件..."
rm -rf build dist

# 3. 执行 PyInstaller 打包
echo "📦 [2/4] 正在执行 PyInstaller，请耐心等待 1-2 分钟..."
python3 -m PyInstaller AiNiee.spec

# 4. 暴力物理补齐资源文件
echo "📂 [3/4] 正在强制复制资源文件夹到 .app 内部..."
cp -R Resource "$APP_MACOS_DIR/"
cp -R ModuleFolders "$APP_MACOS_DIR/"
cp -R PluginScripts "$APP_MACOS_DIR/"

# 5. 修复 M4 芯片的系统权限
echo "🔐 [4/4] 正在修复 M4 架构的文件执行权限..."
chmod -R 755 "$PROJECT_DIR/dist/AiNiee.app"

echo "====================================="
echo "✅ 打包与修复全部完成！大功告成！"
echo "🎉 你的独立软件位置: $PROJECT_DIR/dist/AiNiee.app"
echo "====================================="
echo "👉 测试运行请在终端直接复制并回车执行下面这行代码："
echo "\"$APP_MACOS_DIR/AiNiee\""
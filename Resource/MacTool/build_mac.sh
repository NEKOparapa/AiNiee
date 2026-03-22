#!/bin/bash
set -e

# --- 路径动态识别 ---
# 1. 获取当前脚本所在的目录 (AiNiee/Resource/MacTool)
SCRIPT_DIR=$(cd "$(dirname "$0")"; pwd)
# 2. 向上退两级，精准定位真正的项目根目录 (AiNiee)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/../.."; pwd)

APP_NAME="AiNiee"
# 将输出目录强制绑定在项目根目录，以对接 GitHub Actions 的 DMG 打包步骤
DIST_DIR="$PROJECT_ROOT/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"

echo "🚀 开始自动化打包 $APP_NAME (官方纯净版)..."
echo "📂 经核查，项目根目录识别为: $PROJECT_ROOT"

# 强制切回项目根目录！确保 .spec 文件内的相对依赖不会找错地方
cd "$PROJECT_ROOT"

echo "🧹 [1/4] 正在清理旧的编译缓存..."
rm -rf build dist
mkdir -p "$PROJECT_ROOT/build/$APP_NAME"

echo "📦 [2/4] 正在执行 PyInstaller 打包..."
# 从根目录调用位于 MacTool 下的 .spec 文件
python3 -m PyInstaller "Resource/MacTool/AiNiee.spec"

echo "🩹 [3/4] [强干预] 正在物理注入 PyInstaller 漏掉的静态资源..."
# 建立目标内脏目录
mkdir -p "$APP_BUNDLE/Contents/MacOS/Resource"

# 从真正的根目录拷贝 Resource 文件夹内容
cp -a "$PROJECT_ROOT/Resource/." "$APP_BUNDLE/Contents/MacOS/Resource/"

echo "🔐 [4/4] 正在修复 macOS 架构的文件执行权限..."
chmod -R 755 "$APP_BUNDLE"

echo "✅ 打包彻底完成！软件位置: $APP_BUNDLE"

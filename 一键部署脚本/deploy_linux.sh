#!/usr/bin/env bash
set -euo pipefail
export LANG=en_US.UTF-8

ENV_NAME="airicore"
PY_VERSION="3.11"
PIP_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
PIP_HOST="pypi.tuna.tsinghua.edu.cn"
PLAYWRIGHT_DOWNLOAD_HOST="https://cdn.npmmirror.com/binaries/playwright"
export PLAYWRIGHT_DOWNLOAD_HOST
CONDA_MIRROR="https://mirrors.tuna.tsinghua.edu.cn/anaconda"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "==> AiriCore 一键部署 (Linux)"
echo "    项目目录: $PROJECT_DIR"

find_conda() {
    if command -v conda >/dev/null 2>&1; then
        CONDA_SH="$(conda info --base)/etc/profile.d/conda.sh"
        return 0
    fi
    for base in "$HOME/miniconda3" "$HOME/anaconda3" "/opt/miniconda3" "/opt/conda"; do
        if [ -f "$base/etc/profile.d/conda.sh" ]; then
            CONDA_SH="$base/etc/profile.d/conda.sh"
            return 0
        fi
    done
    return 1
}

install_miniconda() {
    echo "==> 未检测到 conda, 正在安装 Miniconda 到 $HOME/miniconda3"
    local arch installer url tmp
    arch="$(uname -m)"
    case "$arch" in
        x86_64)  installer="Miniconda3-latest-Linux-x86_64.sh" ;;
        aarch64) installer="Miniconda3-latest-Linux-aarch64.sh" ;;
        *) echo "不支持的架构: $arch"; exit 1 ;;
    esac
    tmp="$(mktemp -d)"
    local ok=0
    for base in "$CONDA_MIRROR/miniconda" "https://repo.anaconda.com/miniconda"; do
        url="$base/$installer"
        echo "    从 $base 下载 Miniconda..."
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL "$url" -o "$tmp/miniconda.sh" && ok=1 && break
        else
            wget -q "$url" -O "$tmp/miniconda.sh" && ok=1 && break
        fi
        echo "    该源下载失败, 尝试下一个..."
    done
    if [ "$ok" -ne 1 ]; then
        echo "错误: Miniconda 下载失败 (镜像与官方源均不可用)。"
        rm -rf "$tmp"
        exit 1
    fi
    bash "$tmp/miniconda.sh" -b -p "$HOME/miniconda3"
    rm -rf "$tmp"
    CONDA_SH="$HOME/miniconda3/etc/profile.d/conda.sh"
}

if ! find_conda; then
    install_miniconda
fi

echo "==> 使用 conda: $CONDA_SH"
# shellcheck disable=SC1090
source "$CONDA_SH"

ENV_LIST="$(conda env list || true)"
if printf '%s\n' "$ENV_LIST" | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "==> 环境 '$ENV_NAME' 已存在, 复用"
else
    echo "==> 接受 conda 默认 channel 服务条款 (旧版无此命令则忽略)"
    for ch in \
        "https://repo.anaconda.com/pkgs/main" \
        "https://repo.anaconda.com/pkgs/r" \
        "https://repo.anaconda.com/pkgs/msys2"; do
        conda tos accept --override-channels --channel "$ch" >/dev/null 2>&1 || true
    done
    echo "==> 创建环境 '$ENV_NAME' (python $PY_VERSION, 镜像 channel)"
    if ! conda create -y -n "$ENV_NAME" "python=$PY_VERSION" \
        --override-channels \
        -c "$CONDA_MIRROR/cloud/conda-forge" \
        -c "$CONDA_MIRROR/pkgs/main" \
        -c "$CONDA_MIRROR/pkgs/free"; then
        echo "==> 镜像 channel 失败, 回退官方 conda-forge 重试..."
        if ! conda create -y -n "$ENV_NAME" "python=$PY_VERSION" \
            --override-channels -c conda-forge; then
            echo "错误: 创建 conda 环境失败 (镜像与官方 channel 均失败)。"
            exit 1
        fi
    fi
fi

conda activate "$ENV_NAME"

if [ "${CONDA_DEFAULT_ENV:-}" != "$ENV_NAME" ]; then
    echo "错误: 未能激活环境 '$ENV_NAME', 终止以避免装到错误的 Python。"
    exit 1
fi

pip_install() {
    if python -m pip install "$@" -i "$PIP_INDEX" --trusted-host "$PIP_HOST"; then
        return 0
    fi
    echo "    镜像源失败, 回退官方 PyPI 重试"
    python -m pip install "$@"
}

echo "==> 升级 pip (镜像: $PIP_INDEX, 失败回退官方源)"
pip_install --upgrade pip

echo "==> 安装 requirements.txt 依赖 (镜像: $PIP_INDEX, 失败回退官方源)"
pip_install -r requirements.txt

echo "==> 安装 playwright chromium (镜像: $PLAYWRIGHT_DOWNLOAD_HOST, 失败回退官方源)"
if ! python -m playwright install chromium; then
    echo "    镜像下载失败, 回退官方源重试"
    unset PLAYWRIGHT_DOWNLOAD_HOST
    python -m playwright install chromium || true
fi
if [ "$(id -u)" -eq 0 ] || command -v sudo >/dev/null 2>&1; then
    echo "==> 安装 chromium 系统依赖 (需要 root/sudo)"
    python -m playwright install-deps chromium || true
else
    echo "==> 跳过 chromium 系统依赖 (无 root 且无 sudo), 截图类功能可能不可用"
fi

echo "==> 解压表情包到 meme_generator 包目录"
python "$SCRIPT_DIR/_setup_memes.py" "$PROJECT_DIR"

echo "==> 安装字体 YurukaFangTang.ttf"
FONT_SRC="$PROJECT_DIR/data/nonebot_plugin_meme_stickers/_shared/YurukaFangTang.ttf"
FONT_DIR="$HOME/.local/share/fonts"
if [ -f "$FONT_SRC" ]; then
    mkdir -p "$FONT_DIR"
    cp -f "$FONT_SRC" "$FONT_DIR/"
    if command -v fc-cache >/dev/null 2>&1; then
        fc-cache -f "$FONT_DIR" >/dev/null 2>&1 || true
    fi
    echo "    字体已安装到 $FONT_DIR"
else
    echo "    未找到字体源文件, 跳过: $FONT_SRC"
fi

echo "==> 准备 .env.prod 配置文件"
if [ -f "$PROJECT_DIR/.env.prod" ]; then
    echo "    .env.prod 已存在, 保持不变"
else
    cp "$PROJECT_DIR/.env.prod_example" "$PROJECT_DIR/.env.prod"
    echo "    已从示例创建 .env.prod (启动前请先修改)"
fi

echo "==> 准备自签名 SSL 证书 (bot.py 会加载 ./ssl/)"
SSL_DIR="$PROJECT_DIR/ssl"
if [ -f "$SSL_DIR/privkey.key" ] && [ -f "$SSL_DIR/fullchain.pem" ]; then
    echo "    SSL 证书已存在, 保持不变"
else
    mkdir -p "$SSL_DIR"
    if command -v openssl >/dev/null 2>&1; then
        if openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout "$SSL_DIR/privkey.key" \
            -out "$SSL_DIR/fullchain.pem" \
            -days 3650 -subj "/CN=airicore.local" >/dev/null 2>&1 \
            && [ -s "$SSL_DIR/privkey.key" ] && [ -s "$SSL_DIR/fullchain.pem" ]; then
            echo "    已在 $SSL_DIR 生成自签名证书"
        else
            echo "    警告: openssl 生成证书失败! bot.py 需要 ./ssl/privkey.key 与 ./ssl/fullchain.pem,"
            echo "    请手动生成, 或修改 bot.py 去掉 ssl_keyfile/ssl_certfile 参数, 否则无法启动。"
        fi
    else
        echo "    未找到 openssl; 请手动提供 ./ssl/privkey.key 与 ./ssl/fullchain.pem,"
        echo "    或修改 bot.py 去掉 ssl_keyfile/ssl_certfile 参数。"
    fi
fi

echo "==> 创建运行时目录"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/data"

echo "==> 依赖自检"
if python - <<'PYEOF'
import importlib.util
mods = ["nonebot", "meme_generator", "playwright", "aiohttp", "openai", "numpy", "PIL", "skia", "uvicorn", "psutil", "mcrcon"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    print("    缺失模块: " + ", ".join(missing))
    raise SystemExit(1)
print("    核心依赖齐全")
PYEOF
then :; else
    echo "    警告: 依赖自检未通过, 请回看上面的 pip 报错。"
fi

echo "==> 整理启动脚本"
if [ -f "$PROJECT_DIR/launch_linux.sh" ]; then
    mv -f "$PROJECT_DIR/launch_linux.sh" "$PROJECT_DIR/launch.sh"
    echo "    launch_linux.sh -> launch.sh"
elif [ -f "$PROJECT_DIR/launch.sh" ]; then
    echo "    launch.sh 已存在, 跳过重命名"
else
    echo "    警告: 未找到 launch_linux.sh 或 launch.sh"
fi
chmod +x "$PROJECT_DIR/launch.sh" 2>/dev/null || true
for f in launch_macos.sh launch_windows.bat launch.bat; do
    if [ -e "$PROJECT_DIR/$f" ]; then
        rm -f "$PROJECT_DIR/$f"
        echo "    已删除 $f"
    fi
done

echo ""
echo "==> 部署完成。后续步骤:"
echo "    1. 编辑 .env.prod (SUPERUSERS, ONEBOT_ACCESS_TOKEN, LLM 密钥 等)"
echo "    2. 启动: ./launch.sh"

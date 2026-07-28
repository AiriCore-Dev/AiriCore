#!/usr/bin/env bash
set -euo pipefail
export LANG=en_US.UTF-8

ENV_NAME="airicore"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> AiriCore 一键启动 (Linux)"
echo "    项目目录: $SCRIPT_DIR"

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

if ! find_conda; then
    echo "错误: 未找到 conda。请先运行 一键部署脚本/deploy_linux.sh 完成部署。"
    exit 1
fi

# shellcheck disable=SC1090
source "$CONDA_SH"

if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
    echo "错误: 未找到 conda 环境 '$ENV_NAME'。请先运行 一键部署脚本/deploy_linux.sh 完成部署。"
    exit 1
fi

conda activate "$ENV_NAME"

echo "==> 启动 AiriCore (崩溃后会自动重启, 按 Ctrl+C 退出)"
python bot.py

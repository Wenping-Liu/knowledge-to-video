#!/bin/sh
cd "$(dirname "$0")" || exit 1
for ktv_boot in python3.12 python3.11 python3.13 python3; do
  if command -v "$ktv_boot" >/dev/null 2>&1; then
    "$ktv_boot" scripts/setup.py --yes "$@"
    ktv_status=$?
    printf '\n安装过程已结束。详细结果见上方；失败时可按提示重试。\n'
    if [ -t 0 ]; then printf '按回车关闭窗口'; read -r ktv_line; fi
    exit "$ktv_status"
  fi
done
printf '请先安装 Python 3.12：https://www.python.org/downloads/\n'
exit 1

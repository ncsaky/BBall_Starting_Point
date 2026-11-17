#!/bin/sh
# Run from any directory. uv is a builder dependency, never a player dependency.
set -eu
task_repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$(uname -s)" != Darwin ]; then
    echo 'This private build requires macOS.' >&2
    exit 1
fi
task_arch=$(uname -m)
task_expect_arch=no
for task_arg in "$@"; do
    if [ "$task_expect_arch" = yes ]; then
        task_arch=$task_arg
        task_expect_arch=no
    else
        case "$task_arg" in
            --arch) task_expect_arch=yes ;;
            --arch=*) task_arch=${task_arg#--arch=} ;;
        esac
    fi
done
if [ "$task_expect_arch" = yes ]; then
    echo '--arch requires arm64 or x86_64.' >&2
    exit 1
fi
case "$task_arch" in
    arm64) task_python=cpython-3.12.11-macos-aarch64-none ;;
    x86_64) task_python=cpython-3.12.11-macos-x86_64-none ;;
    *) echo 'Supported architectures: arm64, x86_64.' >&2; exit 1 ;;
esac
if [ "$task_arch" = x86_64 ] && ! arch -x86_64 /usr/bin/true 2>/dev/null; then
    echo 'Install Rosetta 2 on this Apple Silicon builder, or build on an Intel Mac.' >&2
    exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
    echo 'Install uv on the build Mac: https://docs.astral.sh/uv/getting-started/installation/' >&2
    exit 1
fi
task_env="$task_repo/.cache/macos-beta-build/$task_arch/venv"
if [ ! -x "$task_env/bin/python" ]; then
    uv venv --python "$task_python" --managed-python "$task_env"
fi
uv pip install --python "$task_env/bin/python" -r "$task_repo/packaging/macos/build-requirements.txt"
exec "$task_env/bin/python" "$task_repo/packaging/macos/build.py" "$@"

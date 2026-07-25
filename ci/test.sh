#!/usr/bin/env bash
#
# Run the test suite in Docker, reproducing exactly what CI does.
#
# Usage:
#   ./ci/test.sh                          # run all 8 jobs
#   ./ci/test.sh pixi humble              # one pixi job
#   ./ci/test.sh container rolling        # one container job
#   ./ci/test.sh pixi                     # all 4 pixi jobs
#   ./ci/test.sh container                # all 4 container jobs
#
set -euo pipefail

DISTROS=(humble jazzy lyrical rolling)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
BOLD='\033[1m'
RESET='\033[0m'

passed=()
failed=()

run_pixi() {
    local distro=$1
    echo -e "${BOLD}=== pixi / ${distro} ===${RESET}"
    docker run --rm \
        -v "${REPO_ROOT}:/src:ro" \
        -w /build \
        ubuntu:24.04 \
        bash -c "
            set -euo pipefail
            cp -r /src/. .
            # Drop developer-local artifacts copied from the mounted checkout.
            # In particular, a host .pixi env may contain symlinks that are
            # invalid inside this container.
            rm -rf .pixi .pytest_cache .venv pytest_colcon_ws.egg-info
            rm -rf tests/test_ws/build tests/test_ws/install tests/test_ws/log
            rm -f tests/test_ws/.test_ws_setup_ran

            # Install pixi
            apt-get update -qq && apt-get install -y -qq curl ca-certificates > /dev/null 2>&1
            curl -fsSL https://pixi.sh/install.sh | PIXI_NO_PATH_UPDATE=1 bash > /dev/null 2>&1
            export PATH=\"\$HOME/.pixi/bin:\$PATH\"

            pixi run -e ${distro} test
        "
}

run_container() {
    local distro=$1
    echo -e "${BOLD}=== container / ${distro} ===${RESET}"
    docker run --rm \
        -v "${REPO_ROOT}:/src:ro" \
        -w /build \
        "ros:${distro}" \
        bash -c "
            set -euo pipefail
            cp -r /src/. .
            # Drop developer-local artifacts copied from the mounted checkout.
            rm -rf .pixi .pytest_cache .venv pytest_colcon_ws.egg-info
            rm -rf tests/test_ws/build tests/test_ws/install tests/test_ws/log
            rm -f tests/test_ws/.test_ws_setup_ran

            # ros:* images have python3 but not always pip/venv.  Install
            # into a virtualenv to avoid PEP 668 externally-managed-system
            # errors, and use a regular install so older Humble tooling does
            # not need PEP 660 editable-install support.
            apt-get update -qq && apt-get install -y -qq python3-pip python3-venv > /dev/null 2>&1
            python3 -m venv --system-site-packages /tmp/pytest-colcon-ws-venv
            source /tmp/pytest-colcon-ws-venv/bin/activate
            pip install --upgrade pip 'setuptools>=68,<80' wheel
            pip install '.[test]'

            pytest
        "
}

run_job() {
    local backend=$1
    local distro=$2
    local label="${backend}/${distro}"

    if "${backend}" "${distro}"; then
        passed+=("$label")
        echo -e "${GREEN}✓ ${label}${RESET}"
    else
        failed+=("$label")
        echo -e "${RED}✗ ${label}${RESET}"
    fi
    echo
}

# --- Argument parsing ---

backend="${1:-all}"
distro="${2:-}"

case "$backend" in
    pixi)
        if [[ -n "$distro" ]]; then
            run_job run_pixi "$distro"
        else
            for d in "${DISTROS[@]}"; do run_job run_pixi "$d"; done
        fi
        ;;
    container)
        if [[ -n "$distro" ]]; then
            run_job run_container "$distro"
        else
            for d in "${DISTROS[@]}"; do run_job run_container "$d"; done
        fi
        ;;
    all)
        for d in "${DISTROS[@]}"; do run_job run_pixi "$d"; done
        for d in "${DISTROS[@]}"; do run_job run_container "$d"; done
        ;;
    *)
        echo "Usage: $0 [pixi|container|all] [humble|jazzy|lyrical|rolling]"
        exit 1
        ;;
esac

# --- Summary ---

echo -e "${BOLD}=== Summary ===${RESET}"
for label in "${passed[@]+"${passed[@]}"}"; do
    echo -e "  ${GREEN}✓ ${label}${RESET}"
done
for label in "${failed[@]+"${failed[@]}"}"; do
    echo -e "  ${RED}✗ ${label}${RESET}"
done

total=$(( ${#passed[@]} + ${#failed[@]} ))
echo -e "  ${total} jobs: ${#passed[@]} passed, ${#failed[@]} failed"

[[ ${#failed[@]} -eq 0 ]]

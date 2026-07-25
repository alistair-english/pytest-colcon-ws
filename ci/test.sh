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

            # ros:* images have python3 but not always pip
            apt-get update -qq && apt-get install -y -qq python3-pip > /dev/null 2>&1
            pip install -e '.[test]' --break-system-packages 2>/dev/null \
                || pip install -e '.[test]'

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

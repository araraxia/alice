#!/usr/bin/env bash
#
# Deploy script for the Alice Flask application.
#
# Typical usage:
#   sudo ./deploy.sh                # normal deploy
#   sudo ./deploy.sh --dry-run      # show what would happen
#   sudo ./deploy.sh --branch main  # deploy a different branch
#   sudo ./deploy.sh --skip-reqs    # skip requirements install
#
# This script:
#   * Acquires an exclusive lock to prevent concurrent deployments
#   * Records current commit (for rollback)
#   * Fetches and fast-forwards to the target branch
#   * Optionally installs updated Python dependencies
#   * Restarts the systemd service
#   * Performs a health check; rolls back if it fails
#
# REQUIREMENTS:
#   * Run as root (so it can systemctl restart & chown) – it will drop to $APP_USER for git/pip steps.
#   * 'alice' user must have SSH (deploy key) or HTTPS access to the repo.
#   * curl installed for health check.
#
# SECURITY NOTE:
#   Avoid embedding secrets here; use /opt/alice/.env or similar EnvironmentFile in systemd.
#

set -euo pipefail

#####################################
# Configurable variables
#####################################
APP_NAME="alice"
SERVICE_NAME="alice.service"
APP_USER="alice"
REPO_DIR="/opt/alice"
VENV_DIR="/opt/alice/.venv"
DEFAULT_BRANCH="main"
HEALTH_URL="http://127.0.0.1:6969/health"
HEALTH_TIMEOUT=5
CURL_BIN="$(command -v curl)"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
LOCK_FILE="/var/lock/${APP_NAME}_deploy.lock"
LOG_FILE="/var/log/${APP_NAME}_deploy.log"

# Behavior toggles (can be overridden via flags)
DRY_RUN=false
FORCE=false
SKIP_REQS=false
SKIP_HEALTH=false
CREATE_TAG=false
TAG_PREFIX="deploy"
ROLLBACK_ON_FAIL=true
RESTART_MODE="restart"   # or "reload" (Waitress lacks graceful reload → keep restart)

#####################################
# Utility functions
#####################################
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }

log() {
  local level="$1"; shift
  local msg="[$(timestamp)] [$level] $*"
  echo -e "$msg"
  echo -e "$msg" >> "$LOG_FILE"
}

run_as_app_user() {
  if [[ "$DRY_RUN" == "true" ]]; then
    log DRY "sudo -u $APP_USER bash -c '$*'"
  else
    sudo -u "$APP_USER" bash -c "$*"
  fi
}

usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --branch <name>     Deploy specified branch (default: $DEFAULT_BRANCH)
  --force             Allow non fast-forward (reset hard to remote)
  --skip-reqs         Do not install/update Python requirements
  --skip-health       Skip health check and rollback logic
  --dry-run           Show actions without executing
  --no-rollback       Do not rollback on failed health check
  --tag               Create a lightweight git tag after successful deploy
  --restart-mode <m>  restart (default) | none (skip service restart)
  -h, --help          Show this help

Examples:
  $0
  $0 --branch develop --skip-reqs
  $0 --force --tag
EOF
}

#####################################
# Parse arguments
#####################################
DEPLOY_BRANCH="$DEFAULT_BRANCH"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) DEPLOY_BRANCH="$2"; shift 2 ;;
    --force) FORCE=true; shift ;;
    --skip-reqs) SKIP_REQS=true; shift ;;
    --skip-health) SKIP_HEALTH=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --no-rollback) ROLLBACK_ON_FAIL=false; shift ;;
    --tag) CREATE_TAG=true; shift ;;
    --restart-mode) RESTART_MODE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) log ERROR "Unknown argument: $1"; usage; exit 1 ;;
  esac
done

#####################################
# Pre-flight checks
#####################################
if [[ $EUID -ne 0 ]]; then
  log ERROR "Run as root (so we can manage systemd)."
  exit 1
fi

if [[ ! -d "$REPO_DIR/.git" ]]; then
  log ERROR "No git repository at $REPO_DIR"
  exit 1
fi

if [[ ! -x "$PIP_BIN" ]]; then
  log ERROR "Pip not found at $PIP_BIN (is venv set correctly?)"
  exit 1
fi

if [[ -z "$CURL_BIN" && "$SKIP_HEALTH" == "false" ]]; then
  log ERROR "curl not found; install or use --skip-health"
  exit 1
fi

touch "$LOG_FILE" || { log ERROR "Cannot write log file $LOG_FILE"; exit 1; }

#####################################
# Acquire lock
#####################################
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  log ERROR "Another deployment appears to be running (lock $LOCK_FILE)"
  exit 1
fi

log INFO "Starting deploy (branch=$DEPLOY_BRANCH dry_run=$DRY_RUN force=$FORCE skip_reqs=$SKIP_REQS)"

#####################################
# Record current state
#####################################
CURRENT_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"
log INFO "Current commit: $CURRENT_COMMIT"

#####################################
# Fetch latest
#####################################
log INFO "Fetching origin..."
if [[ "$DRY_RUN" == "true" ]]; then
  log DRY "sudo -u $APP_USER git -C $REPO_DIR fetch --prune origin"
else
  run_as_app_user "git -C '$REPO_DIR' fetch --prune origin"
fi

# Ensure branch exists remotely
if ! run_as_app_user "git -C '$REPO_DIR' ls-remote --heads origin $DEPLOY_BRANCH" | grep -q "$DEPLOY_BRANCH"; then
  log ERROR "Remote branch '$DEPLOY_BRANCH' not found on origin"
  exit 1
fi

#####################################
# Determine fast-forward possibility
#####################################
LOCAL_BRANCH_COMMIT=$(git -C "$REPO_DIR" rev-parse "refs/heads/$DEPLOY_BRANCH" 2>/dev/null || echo "")
REMOTE_BRANCH_COMMIT=$(git -C "$REPO_DIR" rev-parse "origin/$DEPLOY_BRANCH")

if [[ -z "$LOCAL_BRANCH_COMMIT" ]]; then
  log INFO "Local branch $DEPLOY_BRANCH does not exist; creating from origin/$DEPLOY_BRANCH"
  run_as_app_user "git -C '$REPO_DIR' checkout -B '$DEPLOY_BRANCH' 'origin/$DEPLOY_BRANCH'"
else
  if git -C "$REPO_DIR" merge-base --is-ancestor "$LOCAL_BRANCH_COMMIT" "$REMOTE_BRANCH_COMMIT"; then
    log INFO "Fast-forward possible."
    run_as_app_user "git -C '$REPO_DIR' checkout '$DEPLOY_BRANCH'"
    run_as_app_user "git -C '$REPO_DIR' merge --ff-only 'origin/$DEPLOY_BRANCH'"
  else
    if [[ "$FORCE" == "true" ]]; then
      log WARN "Non fast-forward; forcing reset (potentially discarding local changes)."
      run_as_app_user "git -C '$REPO_DIR' checkout '$DEPLOY_BRANCH' || git -C '$REPO_DIR' checkout -B '$DEPLOY_BRANCH' 'origin/$DEPLOY_BRANCH'"
      run_as_app_user "git -C '$REPO_DIR' reset --hard 'origin/$DEPLOY_BRANCH'"
    else
      log ERROR "Non fast-forward update required. Re-run with --force to reset."
      exit 1
    fi
  fi
fi

NEW_COMMIT=$(git -C "$REPO_DIR" rev-parse HEAD)
log INFO "Updated to commit: $NEW_COMMIT"

#####################################
# Check for uncommitted changes (should be clean)
#####################################
if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
  log WARN "Repository not clean after update (uncommitted changes present)."
fi

#####################################
# Conditional requirements install
#####################################
REQ_FILE="$REPO_DIR/requirements.txt"
REQ_HASH_FILE="$REPO_DIR/.requirements.sha256"

if [[ -f "$REQ_FILE" && "$SKIP_REQS" == "false" ]]; then
  NEW_HASH=$(sha256sum "$REQ_FILE" | awk '{print $1}')
  OLD_HASH=$(cat "$REQ_HASH_FILE" 2>/dev/null || echo "")
  if [[ "$NEW_HASH" != "$OLD_HASH" ]]; then
    log INFO "Requirements changed; installing dependencies."
    if [[ "$DRY_RUN" == "true" ]]; then
      log DRY "$PIP_BIN install -r $REQ_FILE"
    else
      run_as_app_user "$PIP_BIN install --upgrade -r '$REQ_FILE'"
      echo "$NEW_HASH" > "$REQ_HASH_FILE"
      chown "$APP_USER":"$APP_USER" "$REQ_HASH_FILE"
    fi
  else
    log INFO "Requirements unchanged (hash match); skipping pip install."
  fi
else
  log INFO "Skipping requirements install (skip=$SKIP_REQS or file missing)."
fi

#####################################
# Service restart / reload
#####################################
if [[ "$RESTART_MODE" != "none" ]]; then
  log INFO "Restarting service ($SERVICE_NAME)"
  if [[ "$DRY_RUN" == "true" ]]; then
    log DRY "systemctl restart $SERVICE_NAME"
  else
    systemctl restart "$SERVICE_NAME"
  fi
else
  log INFO "Skipping service restart (RESTART_MODE=none)"
fi

#####################################
# Health check
#####################################
if [[ "$SKIP_HEALTH" == "false" ]]; then
  log INFO "Performing health check: $HEALTH_URL (timeout ${HEALTH_TIMEOUT}s)"
  if [[ "$DRY_RUN" == "true" ]]; then
    log DRY "curl --fail -m $HEALTH_TIMEOUT $HEALTH_URL"
  else
    sleep 2  # brief warm-up
    if ! $CURL_BIN --fail -m "$HEALTH_TIMEOUT" "$HEALTH_URL" >/dev/null 2>&1; then
      log ERROR "Health check FAILED."
      if [[ "$ROLLBACK_ON_FAIL" == "true" ]]; then
        log WARN "Rolling back to previous commit $CURRENT_COMMIT"
        run_as_app_user "git -C '$REPO_DIR' reset --hard '$CURRENT_COMMIT'"
        if [[ "$RESTART_MODE" != "none" ]]; then
          systemctl restart "$SERVICE_NAME" || true
        fi
        if $CURL_BIN --fail -m "$HEALTH_TIMEOUT" "$HEALTH_URL" >/dev/null 2>&1; then
          log INFO "Rollback successful; service healthy again."
        else
          log ERROR "Rollback did not restore health; manual intervention required."
          exit 2
        fi
      else
        log WARN "Rollback disabled (--no-rollback)."
        exit 2
      fi
    else
      log INFO "Health check passed."
    fi
  fi
else
  log INFO "Skipping health check (--skip-health)."
fi

#####################################
# Tagging (optional)
#####################################
if [[ "$CREATE_TAG" == "true" && "$DRY_RUN" == "false" ]]; then
  TAG_NAME="${TAG_PREFIX}-$(date +%Y%m%d-%H%M%S)"
  log INFO "Creating tag $TAG_NAME"
  run_as_app_user "git -C '$REPO_DIR' tag $TAG_NAME $NEW_COMMIT"
  run_as_app_user "git -C '$REPO_DIR' push origin $TAG_NAME || true"
elif [[ "$CREATE_TAG" == "true" && "$DRY_RUN" == "true" ]]; then
  log DRY "git tag ${TAG_PREFIX}-<timestamp> && git push origin <tag>"
fi

log INFO "Deployment complete (new_commit=$NEW_COMMIT)"
exit 0
#!/usr/bin/env bash
set -euo pipefail

# Gets a factory-fresh Mac to the point where the rest of setup can run:
# Homebrew, then the supported Node 24 runtime. Everything downstream (the MCP build, the harness
# CLIs' config writers, the settings merge) needs Node, so this step is fatal
# if it cannot produce one.
#
# setup.sh SOURCES this script rather than executing it, so the PATH change from
# `brew shellenv` is visible to the later steps — setup-ollama.sh in particular
# looks for brew. Run standalone it still installs everything and still updates
# ~/.zprofile; only the current shell's PATH is left untouched.

REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}"
. "$REPO/scripts/common.sh"

BREW_PREFIX="/usr/local"
[ "$(uname -m)" = "arm64" ] && BREW_PREFIX="/opt/homebrew"

# --- git ---
# You needed it to clone this repo, so a failure here means something is badly
# wrong rather than merely unbootstrapped.
command -v git >/dev/null 2>&1 || { err "git is required"; exit 1; }

# --- Homebrew ---
# A brand-new install, or any shell that has not sourced ~/.zprofile yet, has
# brew on disk but not on PATH. Check the prefix before concluding it's absent.
if ! command -v brew >/dev/null 2>&1 && [ -x "$BREW_PREFIX/bin/brew" ]; then
  eval "$("$BREW_PREFIX/bin/brew" shellenv)"
fi

if ! command -v brew >/dev/null 2>&1; then
  log "Homebrew not found — installing it (it will ask for your password)"
  if [ "${DRY_RUN:-0}" = "1" ]; then
    printf '\033[2m[dry-run]\033[0m install Homebrew from https://brew.sh\n'
  else
    # The official installer. NONINTERACTIVE skips its "press RETURN" gate; the
    # sudo prompt remains, which is the real confirmation step.
    if ! NONINTERACTIVE=1 /bin/bash -c \
      "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; then
      err "Homebrew install failed — install it manually from https://brew.sh and re-run"
      exit 1
    fi
    [ -x "$BREW_PREFIX/bin/brew" ] && eval "$("$BREW_PREFIX/bin/brew" shellenv)"
  fi
fi

if command -v brew >/dev/null 2>&1; then
  # The installer prints these two lines as "next steps" but does not run them,
  # so a new terminal would lose brew again.
  shellenv_line="eval \"\$($BREW_PREFIX/bin/brew shellenv)\""
  if [ -f "$HOME/.zprofile" ] && grep -qF "$shellenv_line" "$HOME/.zprofile"; then
    :
  elif [ "${DRY_RUN:-0}" = "1" ]; then
    printf '\033[2m[dry-run]\033[0m append brew shellenv to ~/.zprofile\n'
  else
    printf '\n%s\n' "$shellenv_line" >> "$HOME/.zprofile"
    log "added brew to ~/.zprofile for future shells"
  fi
fi

# --- Node 24 (independent of the system-wide Node version) ---
resolve_halo_node
if [ ! -x "$HALO_NODE" ] || [ ! -x "$HALO_NPM" ]; then
  log "installing Halo's Node 24 runtime via Homebrew"
  if ! run brew install node@24; then
    err "could not install node@24; fix the Homebrew error and re-run setup"
    exit 1
  fi
fi
use_halo_node

if [ "${DRY_RUN:-0}" = "1" ]; then
  log "would use $HALO_NODE for Halo's build and MCP registrations"
else
  log "prerequisites ok (Halo node $("$HALO_NODE" --version))"
fi

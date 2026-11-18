#!/usr/bin/env bash
# Shared helpers, sourced by every script. Not executable on its own.

log()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarn:\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; }

# Mutating commands go through run() so --dry-run can print instead of act.
run() {
  if [ "${DRY_RUN:-0}" = "1" ]; then
    printf '\033[2m[dry-run]\033[0m %s\n' "$*"
  else
    "$@"
  fi
}

# Use Homebrew's stable major-version path, never its moving `node` alias.
resolve_halo_node() {
  if command -v brew >/dev/null 2>&1; then
    HALO_NODE_PREFIX="$(brew --prefix node@24)" || {
      err "cannot resolve Homebrew node@24"
      return 1
    }
  elif [ "${DRY_RUN:-0}" = "1" ]; then
    HALO_NODE_PREFIX="${BREW_PREFIX:-/opt/homebrew}/opt/node@24"
  else
    err "Homebrew is required to locate Halo's Node 24 runtime; run ./setup.sh"
    return 1
  fi
  HALO_NODE="$HALO_NODE_PREFIX/bin/node"
  HALO_NPM="$HALO_NODE_PREFIX/bin/npm"
}

use_halo_node() {
  resolve_halo_node || return 1
  if [ ! -x "$HALO_NODE" ] || [ ! -x "$HALO_NPM" ]; then
    if [ "${DRY_RUN:-0}" != "1" ]; then
      err "Halo requires Homebrew node@24; run ./setup.sh to install it"
      return 1
    fi
  else
    local major
    major="$("$HALO_NODE" -p 'process.versions.node.split(".")[0]')" || return 1
    if [ "$major" != "24" ]; then
      err "expected Node 24 at $HALO_NODE, found major $major"
      return 1
    fi
  fi
  # npm and package lifecycle scripts resolve node through PATH as well.
  export PATH="$HALO_NODE_PREFIX/bin:$PATH"
  export HALO_NODE HALO_NPM
  hash -r
}

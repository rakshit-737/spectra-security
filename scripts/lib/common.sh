#!/usr/bin/env bash
# scripts/lib/common.sh -- shared shell helpers for the SPECTRA root Makefile.
#
# Owner: Part I section 33 (build system) and Part II section 74 (offline build, CI tiering).
# Status: not started, except for the helpers in this file, which are the thing being delivered.
#
# Contract:
#   * This file is SOURCED, never executed. Every make recipe that needs a helper begins with
#     `. "$(COMMON)"`.
#   * It contains logging, the shell side of the not-implemented macro, and toolchain probing.
#     It contains no SPECTRA logic of any kind: no parsing, no kernel, no generator.
#   * Dependency-free: bash builtins plus coreutils only. No jq, no python, no awk, no network.
#   * Deterministic and quiet: TZ=UTC and LC_ALL=C are exported by the Makefile; nothing here
#     reads the wall clock, the hostname or RANDOM into any output that could reach an artifact.
#
# Anything here that cannot be done honestly yet says so and exits non-zero. Nothing here ever
# succeeds while having done nothing.

# Idempotent source guard: sourcing twice must be harmless.
if [ -n "${SPECTRA_COMMON_SH_LOADED:-}" ]; then
  return 0 2>/dev/null || exit 0
fi
SPECTRA_COMMON_SH_LOADED=1

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
# A declared-but-unimplemented target exits 1. It never exits 0 having done nothing.
# TODO(decision: exit-code vocabulary) Part II section 74 references an abi-exitcodes gate for the
# SPECTRA binaries. These Makefile-side codes are deliberately trivial (0 or 1) until that gate
# and its table exist. To change: declare the table in docs/ and update these two constants.
SPECTRA_EXIT_OK=0
SPECTRA_EXIT_FAIL=1
readonly SPECTRA_EXIT_OK SPECTRA_EXIT_FAIL

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Every line carries a bracketed channel so transcripts are greppable and stable. No colour, no
# cursor control, no progress animation: output must be byte-stable when captured.

spectra_log()  { printf '[spectra] %s\n' "$*"; }
spectra_info() { printf '[info]    %s\n' "$*"; }
spectra_warn() { printf '[warn]    %s\n' "$*" >&2; }
spectra_err()  { printf '[error]   %s\n' "$*" >&2; }

spectra_rule() {
  printf -- '--------------------------------------------------------------------------\n'
}

# spectra_die <message...>
# Print an error and exit non-zero. Used where there is nothing honest left to do.
spectra_die() {
  spectra_err "$@"
  exit "$SPECTRA_EXIT_FAIL"
}

# ---------------------------------------------------------------------------
# The not-implemented macro, shell side
# ---------------------------------------------------------------------------
# spectra_not_implemented <target> <spec-section> <what-it-will-do> <milestone>
#
# The single place a declared-but-unbuilt target reports itself. It prints exactly which
# specification section owns the target, what the target will do once it exists, and the milestone
# that implements it, then exits non-zero.
#
# It must never be softened into a warning, never be given a force path, and never exit 0. A
# target that prints "not implemented" and exits 0 is a lie, and a lying target is worse than a
# missing one because CI goes green over it.
spectra_not_implemented() {
  local target="${1:?spectra_not_implemented: missing target name}"
  local section="${2:?spectra_not_implemented: missing spec section}"
  local what="${3:?spectra_not_implemented: missing description}"
  local milestone="${4:?spectra_not_implemented: missing milestone}"

  {
    spectra_rule
    printf 'NOT IMPLEMENTED: make %s\n' "$target"
    spectra_rule
    printf '  owned by    : specification section %s\n' "$section"
    printf '  will do     : %s\n' "$what"
    printf '  implemented : milestone %s\n' "$milestone"
    printf '  status      : not started\n'
    spectra_rule
    printf 'This target is declared so the build system reads as a complete map of the project.\n'
    printf 'It is not built yet, so it exits non-zero rather than exiting 0 having done nothing.\n'
    printf 'Do not make it pass by deleting the assertion. Build it, or leave it red.\n'
  } >&2

  exit "$SPECTRA_EXIT_FAIL"
}

# ---------------------------------------------------------------------------
# Toolchain probing
# ---------------------------------------------------------------------------
# Presence only. Version comparison against the pinned set is NOT implemented here: the pins live
# in .tool-versions (Part I section 33.6) and the image digests live in images.lock (Part II
# section 74.1), which does not exist yet; the comparison itself is unwritten. make doctor says so
# out loud rather than printing a comparison it cannot make.

# spectra_have <command>
# True when the command resolves on PATH.
spectra_have() {
  command -v "${1:?spectra_have: missing command}" >/dev/null 2>&1
}

# spectra_version <command> [version-args...]
# Best-effort single-line version string. Prints nothing when the command does not resolve or
# refuses to report a version. This is a report, never an assertion.
spectra_version() {
  local cmd="${1:?spectra_version: missing command}"
  shift
  spectra_have "$cmd" || return 0
  if [ "$#" -eq 0 ]; then
    set -- --version
  fi
  # A toolchain that exits non-zero on --version is still present; do not let it kill the probe.
  "$cmd" "$@" 2>&1 | head -n 1 | tr -d '\r' || true
}

# spectra_probe <label> <command> [version-args...]
# Print one fixed-width row describing whether a toolchain is present; return 0 when it is.
# The row shape is normative for make doctor. Keep it stable so transcripts diff cleanly.
spectra_probe() {
  local label="${1:?spectra_probe: missing label}"
  local cmd="${2:?spectra_probe: missing command}"
  shift 2

  if spectra_have "$cmd"; then
    printf '  %-16s %-8s %s\n' "$label" "present" "$(spectra_version "$cmd" "$@")"
    return "$SPECTRA_EXIT_OK"
  fi

  printf '  %-16s %-8s %s\n' "$label" "MISSING" "no ${cmd} on PATH"
  return "$SPECTRA_EXIT_FAIL"
}

# ---------------------------------------------------------------------------
# Host facts
# ---------------------------------------------------------------------------
# Measured, never compared against a target. Part II section 74.10 declares WSL2 and Docker
# Desktop resource profiles (core / matrix / range) and explicitly marks every figure in that
# table as illustrative rather than a target. Those figures are therefore not copied here, and
# make doctor does not gate on them.
#
# TODO(decision: resource profile minimums) When docs/dev/windows.md declares real measured
# minimums, add spectra_require_profile <profile> here and have make doctor exit non-zero with the
# exact .wslconfig edit required, per section 74.10.4.

spectra_host_cpus() {
  if spectra_have nproc; then nproc; else printf 'unknown\n'; fi
}

spectra_host_mem_kb() {
  if [ -r /proc/meminfo ]; then
    sed -n 's/^MemTotal:[[:space:]]*\([0-9]*\) kB$/\1/p' /proc/meminfo | head -n 1
  else
    printf 'unknown\n'
  fi
}

spectra_host_disk_free() {
  local path="${1:-.}"
  if spectra_have df; then
    df -Ph "$path" 2>/dev/null | sed -n '2p' | tr -s ' ' | cut -d ' ' -f 4
  else
    printf 'unknown\n'
  fi
}

spectra_host_sandbox() {
  local uname_s
  uname_s="$(uname -s 2>/dev/null || printf 'unknown')"
  if [ -n "${SPECTRA_DEVCONTAINER:-}" ]; then
    printf 'devcontainer (%s)\n' "$uname_s"
  elif grep -qi microsoft /proc/version 2>/dev/null; then
    printf 'wsl2 (%s)\n' "$uname_s"
  elif [ -n "${CI:-}" ]; then
    printf 'ci (%s)\n' "$uname_s"
  else
    printf '%s\n' "$uname_s"
  fi
}

# ---------------------------------------------------------------------------
# Layout assertions
# ---------------------------------------------------------------------------
# Used by make skeleton-verify. These check existence only. They do not read file contents, do not
# validate schemas, and make no claim about whether the contents are correct or complete.

# spectra_require_dir <path>
spectra_require_dir() {
  local path="${1:?spectra_require_dir: missing path}"
  if [ -d "$path" ]; then
    printf '  %-6s dir   %s\n' "ok" "$path"
    return "$SPECTRA_EXIT_OK"
  fi
  printf '  %-6s dir   %s\n' "MISS" "$path"
  return "$SPECTRA_EXIT_FAIL"
}

# spectra_require_file <path>
spectra_require_file() {
  local path="${1:?spectra_require_file: missing path}"
  if [ -f "$path" ]; then
    printf '  %-6s file  %s\n' "ok" "$path"
    return "$SPECTRA_EXIT_OK"
  fi
  printf '  %-6s file  %s\n' "MISS" "$path"
  return "$SPECTRA_EXIT_FAIL"
}

# spectra_note_owed <path> <owing-milestone>
# For artefacts a later milestone owes. Reports presence without asserting it, so skeleton-verify
# can be informative about the future without pretending it is checking it.
spectra_note_owed() {
  local path="${1:?spectra_note_owed: missing path}"
  local milestone="${2:?spectra_note_owed: missing milestone}"
  if [ -e "$path" ]; then
    printf '  %-6s owed  %s (present; not checked here; owed by %s)\n' "--" "$path" "$milestone"
  else
    printf '  %-6s owed  %s (absent; owed by %s)\n' "--" "$path" "$milestone"
  fi
  return "$SPECTRA_EXIT_OK"
}

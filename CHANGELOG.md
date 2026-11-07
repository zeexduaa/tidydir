# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Report damaged lines in `.tidydir/history.jsonl` with line numbers and exit code 1 instead of crashing with a traceback (#34).

### Added

- `exclude` patterns, under `[settings]` (applies to every rule) and per rule.
- Built-in rules now skip unfinished downloads (`*.part`, `*.crdownload`, `*.download`), `*.tmp` and Office lock files (`~$*`).

## [0.1.0] - 2026-11-03

### Added

- `init`, `plan`, `run`, `undo` and `history` commands.
- TOML rules matching by extension, glob, regex, size and age.
- Destination placeholders `{ext}`, `{year}`, `{month}`, `{day}`, `{rule}`.
- Built-in default rules when no `tidydir.toml` is present.
- Name-clash handling (`rename` or `skip`); files are never overwritten.
- Undo journal in `.tidydir/history.jsonl`, including partial runs.

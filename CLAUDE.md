# CLAUDE.md — openClaw

This file provides context, conventions, and guidance for AI assistants (including Claude) working in this repository.

## Project Overview

**openClaw** is an open-source reimplementation of the 1997 2D platformer game *Claw* by Monolith Productions. The project goal is a faithful, cross-platform recreation of the original game engine written in modern C++, allowing the game to run with the original game assets on current operating systems.

This repository is a fork/mirror of [openclaw/openclaw](https://github.com/openclaw/openclaw).

## Repository State

As of the initial commit, this repository contains only a `README.md`. Development has not yet been added to this fork. When source code is introduced, update the relevant sections of this file to reflect the actual structure and build instructions.

## Expected Technology Stack

Based on the upstream project, the expected stack is:

| Component | Technology |
|---|---|
| Language | C++11/14 |
| Build system | CMake |
| Graphics / Input / Audio | SDL2, SDL2_image, SDL2_mixer, SDL2_ttf |
| Physics | Box2D |
| XML parsing | TinyXML2 |
| Scripting | Lua (via LuaBridge) |
| Platform targets | Linux, Windows, macOS |

## Repository Structure (anticipated)

Once source code is committed, the layout is expected to resemble:

```
openclaw/
├── CMakeLists.txt          # Root CMake build definition
├── cmake/                  # CMake helper modules
├── src/
│   ├── Engine/             # Core game engine (actor, physics, rendering, audio)
│   ├── Game/               # Game-specific logic, actors, levels
│   ├── Editor/             # Level/map editor (OpenClawEditor)
│   └── main.cpp            # Entry point
├── resources/              # Game assets (maps, sprites, audio) NOT included in repo
│   └── ASSETS_REQUIRED.md  # Instructions for obtaining original game assets
├── test/                   # Unit / integration tests
└── CLAUDE.md               # This file
```

> Assets (levels, sprites, audio) from the original *Claw* game are copyrighted by Monolith Productions and are **not** distributed in this repository. Players must supply their own copy of the original game.

## Building the Project

### Prerequisites

```bash
# Ubuntu / Debian
sudo apt-get install cmake libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev \
     libsdl2-ttf-dev liblua5.3-dev

# Arch Linux
sudo pacman -S cmake sdl2 sdl2_image sdl2_mixer sdl2_ttf lua

# macOS (Homebrew)
brew install cmake sdl2 sdl2_image sdl2_mixer sdl2_ttf lua
```

### Build Steps

```bash
mkdir build && cd build
cmake ..
make -j$(nproc)
```

### Running

```bash
./openclaw
```

The binary expects game asset files (`.wwd`, `.pid`, `.wav`, etc.) from an original *Claw* installation. Set the asset path via the config file or `--assets` flag.

## Development Workflow

### Branching

- `main` — stable, reviewed code only
- `feature/<short-name>` — new features
- `fix/<short-name>` — bug fixes
- `claude/<task-description>` — branches created by AI assistants (this convention)

### Commit Messages

Use imperative mood, present tense:

```
Add enemy patrol AI for lizard guard actor
Fix collision resolution for sloped tiles
Refactor audio manager to use RAII handles
```

Scope prefixes are optional but helpful: `engine:`, `game:`, `editor:`, `build:`, `test:`.

### Pull Requests

- Link the relevant issue if one exists.
- Include a short description of what changed and why.
- Ensure the project builds and tests pass before requesting review.

## Code Conventions

### C++ Style

- **Standard**: C++11 minimum; C++14 features are acceptable.
- **Naming**:
  - Classes: `PascalCase`
  - Methods and functions: `PascalCase` (consistent with the upstream codebase)
  - Member variables: `m_camelCase`
  - Local variables: `camelCase`
  - Constants / enums: `UPPER_SNAKE_CASE`
- **Headers**: Use `#pragma once` (not include guards).
- **Includes**: Sort as stdlib → third-party → project-local, separated by blank lines.
- **Smart pointers**: Prefer `std::unique_ptr` / `std::shared_ptr` over raw owning pointers.
- **RAII**: Manage all resources (file handles, SDL objects, Box2D bodies) through RAII wrappers.
- **Comments**: Only when the *why* is non-obvious. No restating what the code already says.

### CMake

- Avoid `file(GLOB ...)` for source lists; enumerate source files explicitly.
- Use target-based commands (`target_include_directories`, `target_link_libraries`) rather than the legacy global equivalents.

### Error Handling

- Use return codes or result types for recoverable errors.
- Assert liberally in debug builds for invariants that must never be violated.
- Log errors via the project's logging facility rather than raw `std::cerr`.

## Testing

When tests exist, run them with:

```bash
cd build
ctest --output-on-failure
```

Prefer unit tests for pure logic (physics helpers, XML parsing, math utilities). Integration tests cover subsystem interactions.

## Key Files for AI Assistants

When navigating this codebase, these files are typically the most important starting points:

| File | Purpose |
|---|---|
| `CMakeLists.txt` | Build graph — understand all targets and dependencies |
| `src/main.cpp` | Entry point — startup sequence |
| `src/Engine/GameApp.cpp` | Application lifecycle, subsystem init/teardown |
| `src/Engine/Actor/Actor.cpp` | Base actor class used throughout the game |
| `src/Engine/Physics/PhysicsComponent.cpp` | Box2D integration layer |
| `src/Game/GameLogic.cpp` | Game-specific state machine |

## Constraints and Gotchas

- **Asset licensing**: Never commit original *Claw* game assets. The `.gitignore` should exclude all `.wwd`, `.pid`, `.wav`, `.mid`, and `.res` files.
- **Cross-platform paths**: Use `SDL_GetBasePath()` / project path helpers rather than hardcoded separators.
- **Box2D units**: The physics world uses metres (1 tile ≈ 0.5–1 m). Do not mix pixel and physics coordinates without the conversion factor.
- **SDL threading**: SDL rendering and event polling must remain on the main thread.
- **Lua state**: The Lua VM is not thread-safe; all script calls must be serialised through the main game loop.

## Updating This File

This file should be updated whenever:
- A new major subsystem is added or removed.
- The build system or dependency list changes.
- New conventions are adopted by the team.
- Tooling (linters, formatters, CI) is added.

Last updated: 2026-05-19

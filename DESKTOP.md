# BlockAtelier Desktop for macOS

BlockAtelier Desktop opens in its own native macOS window. It uses the system WebKit renderer for the existing interface and starts a private Python service on the loopback interface. An external browser, terminal, or separately installed Python environment is not required by the packaged application.

## Requirements

- Apple Silicon Mac (M1 or later).
- macOS 14 or later for this build.
- Ollama or a compatible API service is optional for model-backed generation.
- Blender is optional for Blender rendering and is not included in the app.

## Running

Open `BlockAtelier.app`. On first launch, choose **Download & start** to prepare the Minecraft Java 1.21.11 rendering profile. This requires an internet connection. Later launches reuse the local profile. The initial configuration uses the offline demonstration generator. The header switches between Simplified Chinese and English. Download actions use a native Save dialog; Blender scripts can be copied to the macOS clipboard.

User data is stored in `~/Library/Application Support/BlockAtelier/`, outside the application bundle. This includes `config.json`, `library.db`, `builds/`, `uploads/`, `refs/`, `desktop.json`, `data/`, `webview/`, and `desktop.log`. Replacing the app does not replace this data. Configuration can contain API keys in plaintext and should be treated as private.

The desktop library starts separately from the development checkout. To reuse an existing development workspace, quit both versions and copy its contents into the application-support directory, preserving a backup first. Alternatively, launch the source desktop entry point with `ATELIER_WORKSPACE` pointing to the existing workspace.

Ollama runs separately on the same computer; select `ollama`, enter a locally installed model identifier, and use `http://localhost:11434/v1`. Blender can be configured in settings; the standard `/Applications/Blender.app` installation is detected when present.

To use opencode as the app's model source, install opencode 2.x and log in to your provider, then select **opencode** in Model and Rendering Settings. Enter `provider/model` or leave the model blank for opencode's default. Set **opencode executable** to its absolute path if needed; standard OpenCode and Homebrew locations are detected even when Finder does not supply a shell PATH. No API key or endpoint is needed in BlockAtelier for this source. The web and desktop interfaces use the same adapter, including reference-image and visual-review support for image-capable models. This model-source option is independent of the MCP server mode below.

## MCP server mode

The application executable also serves the BlockAtelier MCP tools over stdio, for clients such as opencode, Codex, or Claude Code. No window opens in this mode, and no separate Python installation is needed:

```bash
opencode mcp add blockatelier --global -- /Applications/BlockAtelier.app/Contents/MacOS/BlockAtelier --mcp
```

Adjust the path if the application is stored elsewhere. Clients configured through JSON or TOML use the executable as the command and `--mcp` as its only argument.

MCP mode runs the same bundled `atelier` core as the window and uses the same storage directory, so it shares the configuration, the rendering profile, and the build library. Builds created by a connected client appear in the desktop library; reopen or refresh the library to see them. Open the application once before first use so the rendering profile is installed. Diagnostics are written to `mcp.log` in the application-support directory. `ATELIER_WORKSPACE` and `ATELIER_DATA` override the storage locations.

## Building from source

The lockfile records the Python 3.14 build environment used for this release. Public application bundles exclude game-derived version profiles. They are prepared on the user’s computer at first launch. Game-derived resources are outside the source-code license.

```bash
python -m pip install -r requirements-desktop-lock.txt
python run_desktop.py
python -m PyInstaller --noconfirm BlockAtelier.spec
```

`BlockAtelier.spec` targets Apple Silicon macOS. Build on macOS using an arm64 Python environment. The resulting application is under `dist/BlockAtelier.app`. The build does not include workspace data, API keys, game-derived profiles, Ollama model weights, Blender, or development examples.

`BUNDLED_DEPENDENCIES.md` records the environment used for the packaged build; the corresponding license texts are in `BUNDLED_LICENSES/`. The standard project license files also accompany the application.

## Distribution status

This build has an ad-hoc signature. It has not been notarized with an Apple Developer account. Wider distribution requires an appropriate signing/notarization process and review of the included game-derived resources. Do not disable system-wide security settings to run an application.

If startup fails, check `desktop.log` in the application-support directory. Existing browser mode remains available through `python run.py`.

<div align="center">
  <a href="https://github.com/NEKOparapa/AiNiee-chatgpt">
    <img src="https://github.com/NEKOparapa/AiNiee-chatgpt/blob/main/Example%20image/logo.png" width=60% >
  </a>
</div>


<div align="center">
  
![GitHub stars](https://img.shields.io/github/stars/NEKOparapa/AiNiee?style=flat)  
![GitHub all releases downloads](https://img.shields.io/github/downloads/NEKOparapa/AiNiee/total?style=flat&color=orange)  
![Yesterday Activity](https://img.shields.io/endpoint?url=https://ai-niee-vercel.vercel.app/api/stats%3Ftype%3Dyesterday) 
![Average Activity](https://img.shields.io/endpoint?url=https://ai-niee-vercel.vercel.app/api/stats%3Ftype%3Daverage)

</div>

---


## Introduction🧾 

  
<div align="center">
<strong>AiNiee</strong> is a tool specializing in AI translation,<br>enabling one-click automatic translation of complex long-text content such as games, books, subtitles, and documents.
</div>

*   **All-in-One Format Support, Broad Coverage**
    *   🎮 **Game Translation**: In-depth support for game text export tools like Mtool, Renpy, Translator++, ParaTranz, VNText, and SExtractor.
    *   📚 **Diverse Support**: Effortlessly processes I18Next data, Epub/TXT e-books, Srt/Vtt/Lrc subtitles, Word/PDF/MD documents, and more.

*   **Smart & Efficient, Saves Time & Effort**
    *   🚀 **Complete Workflow**: Open a local project, configure providers and prompts, then translate, check, proofread and export.
    *   ⏱️ **Resumable Tasks**: Follow live progress and logs, stop a task and continue its remaining items.

*   **Optimized for Long Texts, Exceptional Quality**
    *   🎯 **Overcoming Limitations**: Employs techniques like streamlined translation formats, chain-of-thought translation, AI glossaries, and contextual awareness to ensure coherence and accuracy in long-text translations.

    *   💎 **Quality Focus**: Supports prompt adjustments for basic instructions, character introductions, background settings and translation styles, alongside polishing and terminology extraction.

---

## This branch: a local web workspace

The backend runs as an independent Python 3.12 / FastAPI process. The React application in `frontend/` communicates with it over REST and WebSocket. The browser provides API management, project overview, proofreading, prompts, shared tables, quality checks, analysis, export and task logs. The interface defaults to Simplified Chinese and supports English, light and dark themes.

One translation, polishing or analysis task runs at a time. The assistant panel is a placeholder; use `Ctrl+L` to toggle it. Audio, video and image translation are outside this branch's scope. The Windows portable package uses PyInstaller to bundle the backend and serve the built frontend; double-clicking opens the workspace in your default browser. [Earlier releases](https://github.com/NEKOparapa/AiNiee/releases) may have a different interface and startup procedure.

### Install dependencies

Prepare **64-bit Python 3.12**, **Node.js 24** and npm. Run the following from this branch's repository root, containing `AiNiee.py`, `Server/` and `frontend/`. These Windows examples use PowerShell and do not require activating the virtual environment.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install --no-deps -r requirements_no_deps.txt
npm --prefix frontend ci
```

The Python dependencies are intentionally split across two files: install `requirements.txt` first, followed by `requirements_no_deps.txt` with `--no-deps`. Do not replace the latter with ordinary dependency resolution. Use `npm ci` to install from the committed frontend lockfile.

On macOS / Linux, create the environment with `python3.12 -m venv .venv` and replace `.venv\Scripts\python.exe` with `.venv/bin/python` in the Python commands. Your operating system and architecture must also satisfy the individual Python dependencies' installation requirements.

### Start the development environment

Run the frontend in terminal one:

```powershell
npm --prefix frontend run dev
```

Run the backend in terminal two:

```powershell
.venv\Scripts\python.exe AiNiee.py --dev
```

The frontend uses `http://127.0.0.1:5173`; the backend defaults to `http://127.0.0.1:8000`. Once the backend is ready, `--dev` opens the browser and passes its address and access token to the frontend through the URL fragment. **It does not start the frontend process.** Keep both processes running.

The backend prints the following when ready:

```text
TOKEN <random-access-token>
READY <actual-listening-port>
```

You can also open the frontend manually and enter the backend address and `TOKEN` in the connection settings at the top right. This access token authenticates the local connection and is separate from a translation provider's API key. Connection details are stored in the current browser session.

| Argument | Behavior |
| --- | --- |
| `--host 127.0.0.1` | The only permitted listening address; also the default. |
| `--port 8000` | Set the backend port. Source runs default to `8000`; packaged runs default to `0` to choose a free port. Console runs print the selected port in `READY`. |
| `--token <token>` | Use a specified token. Omit it to generate one. A specified token is not printed as a `TOKEN` line. |
| `--dev` | Open the fixed frontend address, `http://127.0.0.1:5173`, after startup. |
| `--web` | Serve `frontend/dist/` and open the workbench on the backend's own origin. Enabled by default in packaged runs; mutually exclusive with `--dev`. |
| `--no-browser` | Do not open a browser or show native startup notifications; intended for automated checks. |

If the backend port is occupied, select another port; keep the frontend on `5173`. Use `Ctrl+C` in the backend terminal to shut down. Shutdown waits for task cleanup and final cache saving.

### Build and preview locally

```powershell
npm --prefix frontend run build
npm --prefix frontend run preview
```

The build is written to `frontend/dist/`. Preview also listens on `http://127.0.0.1:5173`, so stop any development server already using that port. Run the backend in another terminal and connect as above.

Alternatively, serve the built frontend directly from the backend without running Vite:

```powershell
npm --prefix frontend run build
.venv\Scripts\python.exe AiNiee.py --web --port 0
```

The browser opens a random loopback port after startup. The token is passed through the URL fragment and removed from the address bar as soon as the frontend reads it. Reloading a deep link such as a settings page works too.

### Windows portable package

After installing the Python 3.12 and Node.js 24 dependencies above on Windows x64, run this from a complete Git checkout:

```powershell
.venv\Scripts\python.exe Tools/pyinstall.py
```

The script builds the frontend, then produces a PyInstaller folder package with a hidden console and a ZIP. Outputs live under `dist/windows-<UTC-time>-<random-ID>/`: run `AiNiee/AiNiee.exe`, distribute `AiNiee-<version>-windows-x64.zip`, and use its adjacent `.sha256` file to check integrity. The terminal prints the actual `EXECUTABLE`, `PACKAGE` and `SHA256`. Each build uses a new directory without replacing older packages. Use `--console` for a visible diagnostic console or `--skip-frontend-build` to reuse an already built `frontend/dist/`, which is still validated.

Extract the entire ZIP, keep `AiNiee.exe`, `_internal/` and `portable.txt` together, then double-click `AiNiee.exe`. Python, Node.js and a separate frontend server are not needed to run it. The application listens only on `127.0.0.1`, generates a random port and token by default, and opens your default browser when ready. A second launch displays an already-running notification.

Closing the tab leaves background work running. To stop the application, choose **Exit application** on **About / updates** and confirm. The backend stops work, waits for the current request to finish, saves the cache and then exits. The page's “Exit request accepted” message means shutdown has started; it does not claim the process has already exited. Source runs also support this button or `Ctrl+C` in the backend terminal.

The package includes application resources and empty default configuration, without the builder's user configuration, caches or logs. `build-info.json` records the revision, dependencies and resource hashes. A writable portable directory creates `Resource/config.json`, `ProjectCache/` and `Logs/` beside the EXE after first startup. When upgrading, exit the application, preserve configuration and caches from the old folder, and copy them to the corresponding paths in the new package root. Do not put them under `_internal/` or replace existing settings with defaults. An unwritable portable directory falls back to the existing user-data location rules.

### Manual workflow

1. Add and test a provider in API platforms, then assign providers for translation, polishing and analysis.
2. Enter a local project path on Home or select a folder with the directory browser. Choose a project type as needed and open it. If a browser cannot obtain an absolute path from a dropped folder, use path entry or directory browsing; source files are not uploaded or copied.
3. Configure task settings, output, prompts and shared tables. Start translation from the task bar; follow progress, open logs, stop and continue the task.
4. Run rule, language or terminology checks. Select an issue to jump to its highlighted item and edit it. Proofreading supports search, regular expressions, filters, selection and pagination, with only visible rows rendered while scrolling.
5. Choose an output folder in Export to write translated and bilingual files or save the cache manually. Analysis lets you organize characters, terms and exclusions and add selected results to shared tables.

Shared tables support multiple subtables and JSON/XLSX import/export; analysis interchange uses JSON. The prompt library manages custom prompts for translation, polishing and both analysis stages. Project history retains caches for resuming work. Deleting a history entry deletes that project's cache after confirmation; the current project cannot be deleted.

### Configuration, caches and upgrades

Existing `config.json` and `CacheManager` project formats are retained. Source runs default to a portable layout when the repository directory is writable:

| Data | Default location |
| --- | --- |
| User configuration and provider settings | `Resource/config.json` |
| Project caches and translation progress | `ProjectCache/<project-id>/` |
| Runtime logs | `Logs/` |

Keep the configuration and the entire `ProjectCache/` directory when upgrading the source, and continue using the same data paths. Do not replace existing configuration with a sample file. Input and output paths remain in the configuration. When automatic output paths are enabled, translation output goes to `AiNieeOutput/` beside the input directory; polishing output goes to `AiNieePolishOutput/`.

Set `AINIEE_USER_DATA_DIR` to choose the configuration directory containing `config.json`, `AINIEE_PROJECT_CACHE_DIR` for project caches, or `AINIEE_LOG_DIR` for logs. On Windows, `AINIEE_PORTABLE=0` defaults to `%LOCALAPPDATA%/AiNiee/`; non-portable macOS configuration defaults to `~/Library/Application Support/AiNiee/`. Move the existing configuration and caches together when changing data paths.

Inspect the paths resolved by your current environment from the repository root:

```powershell
.venv\Scripts\python.exe -c "from ModuleFolders.Config.FilePathConfig import config_path, project_cache_root, user_log_dir; print(config_path()); print(project_cache_root()); print(user_log_dir())"
```

### Local access and API contracts

`GET /health` is public. With `--web` or the portable package, frontend static resources in the build directory also allow unauthenticated `GET/HEAD` so the browser can load the workbench; this exception does not expose user configuration, project files or APIs. Other HTTP requests, including OpenAPI, require `Authorization: Bearer <token>`; WebSocket uses `/api/v1/ws?token=<token>`. Allowlisted `OPTIONS` preflight requests are exempt, while actual API requests remain authenticated. Browser origins are restricted to `http://127.0.0.1:5173`, `http://localhost:5173` and the backend's own address. Wildcard CORS and remote listening are not supported. Do not share links containing the access token.

REST endpoints are under `/api/v1/`. WebSocket pushes progress, logs and data changes. After a disconnect, the frontend reconnects and refetches current state; missed events are not replayed. Frontend API types and WebSocket contracts are generated from backend Pydantic / OpenAPI definitions. After changing an interface, run:

```powershell
.venv\Scripts\python.exe -m Server.export_openapi
npm --prefix frontend run generate:api
npm --prefix frontend run check:api
```

Commit both `openapi.json` and `frontend/src/api/generated/schema.d.ts`. Do not edit generated files manually.

### Development checks and tests

```powershell
.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run check:api
```

Before the first browser test run, install Playwright's Chromium from `frontend/`:

```powershell
cd frontend
npx playwright install chromium
npm run build
npm run test:e2e
```

Playwright starts or reuses this project's frontend on `5173` and launches test backends with temporary data directories. It uses Python from the repository's `.venv` by default; override the executable with `AINIEE_TEST_PYTHON`. Tests use fixed model mocks and forbid real model requests. Configuration, caches and outputs are isolated from user data. Failure screenshots and traces are saved in `frontend/test-results/`.

`hosted-workbench.spec.ts` loads `frontend/dist/` from the backend and verifies deep-link reloads, token handoff, saved settings and confirmed exit. To run that test against a package, set `AINIEE_TEST_EXECUTABLE` to the absolute path of the built `AiNiee.exe` from the `frontend/` directory and select only that spec:

```powershell
# Replace this with the EXECUTABLE path printed by the build.
$env:AINIEE_TEST_EXECUTABLE = 'D:\packages\AiNiee\AiNiee.exe'
npm run test:e2e -- hosted-workbench.spec.ts
Remove-Item Env:AINIEE_TEST_EXECUTABLE
```

Executable verification does not start Vite or use the source resource directory, so it checks the bundled frontend. This test makes no model calls and cannot be combined with provider mocks. Clear the environment variable before running the complete suite.

For the complete portable-package check, run this from the repository root, replacing `--bundle` with the directory containing the built `AiNiee.exe`:

```powershell
.venv\Scripts\python.exe Tools/smoke_package.py --bundle 'D:\packages\AiNiee' --report build/package-smoke.json
```

The script copies the bundle to a temporary path containing Chinese characters and spaces, uses an isolated user directory and a fixed local OpenAI mock, and verifies stopping, restart recovery, checks, editing, export and log redaction in the real EXE. It also checks no-argument startup, a random port and browser handoff through a temporary `BROWSER` capture command without changing the system default browser. Results are written to JSON; the original distributable receives no user data.

Backend tests compare exported bytes from the old invocation path and the Application path, and exercise stopping, saving, restoring and continuing work. Browser tests cover translation, checks, editing and export, plus shared tables, prompts, analysis and settings.

Browser tests also create a real 50,000-item project and check pagination, virtual scrolling, filtering and persisted edits. Each run writes project loading and interaction timings, scroll frame intervals and rendered row counts to `large-project-performance.json` in its test directory under `frontend/test-results/`. These measurements support regression comparisons; they depend on the machine and do not guarantee the same speed on every device.

GitHub Actions uses Windows, Python 3.12 and Node.js 24 to run backend tests, frontend unit tests and builds, generated type checks, and Playwright workflows, then upload test diagnostics. CI performs checks and builds only; it no longer publishes the old desktop package.

### Current limitations

- Only one task runs at a time; the assistant panel remains a placeholder.
- The existing local-model automatic `/slots` discovery has no timeout. Stopping or shutting down during discovery must wait for that call to return.
- The cache does not store the task mode, so a restart does not automatically restore polishing mode. Polishing can be stopped and continued within the same running instance.
- The task bar shows `—` for cost when the provider supplies no billing data.

---

<details>
<summary>

## Feature Description[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#feature-description)
</summary>

The following historical guides explain the underlying features. For this branch's browser interface, follow the workflow above.



<details>
<summary>

### Settings Description
</summary>

- [Feature - API Management](https://github.com/NEKOparapa/AiNiee/wiki/%E5%8A%9F%E8%83%BD%E2%80%90%E6%8E%A5%E5%8F%A3%E7%AE%A1%E7%90%86)

</details>



<details>
<summary>

### Table Description
</summary>

- [Table - AI Glossary](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90AI%E6%9C%AF%E8%AF%AD%E8%A1%A8%E4%BB%8B%E7%BB%8D)
- [Table - AI Do Not Translate List](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90AI%E7%A6%81%E7%BF%BB%E8%A1%A8%E4%BB%8B%E7%BB%8D)
- [Table - Text Replacement](https://github.com/NEKOparapa/AiNiee/wiki/%E8%A1%A8%E6%A0%BC%E2%80%90%E6%96%87%E6%9C%AC%E6%9B%BF%E6%8D%A2%E4%BB%8B%E7%BB%8D)

</details>



<details>
<summary>

### Other Notes
</summary>

* `Multiple Key Rotation`
  > If you want to use multiple keys to distribute the load and speed up translation based on the number of keys, please use keys from the same account type. When inputting, add an English comma between each key, without line breaks. For example: key1,key2,key3

* `Batch File Translation`
  > Simply place all files that need translation into the input folder. It also supports multi-folder structures.

* `Configuration Migration`
  > See “Configuration, caches and upgrades” above. Keep both the configuration and project caches to retain settings and translation progress.

</details>





</details>

---

<details>
<summary>

## Contribution Guidelines[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#contribution-guidelines)  
</summary>



* **`Improve or Add Supported Files`**: File handling lives in `ModuleFolders/Domain/`; see the [reader/writer development guide](ModuleFolders/Domain/FileAccessor/README.md). This separation project preserves that business logic. Application services belong in `ModuleFolders/Application/`; HTTP routes only validate and delegate. Frontend workspaces live in `frontend/src/workspaces/`, with navigation registered centrally in `registry.ts`.

* **`Improve the Regex Library`**: A comprehensive regex library will greatly help with in-game embedding work and benefit future game translation work and other translation users. The regex library is in the [Resource\Regex](https://github.com/NEKOparapa/AiNiee/blob/main/Resource/Regex/regex.json) folder

* **`Improve Interface Translation`**: Shared frontend strings live in `frontend/src/i18n/`, and workspace strings in their respective `translations.ts` files. Include Simplified Chinese and English for new interface text.

* **`Tests and License`**: Run the checks above before submitting changes and use fixed mocks for model calls. Follow the AGPL-3.0 terms in [LICENSE](LICENSE).

</details>


---

## Special Statement[![](https://raw.githubusercontent.com/aregtech/areg-sdk/master/docs/img/pin.svg)](#special-statement)   
AiNiee's continuous development and iteration to this day is due to ongoing personal research and development of key functional frameworks since the project's inception, user feedback and suggestions, and the joint efforts and creations of contributors through PRs.
This is a process of continuous exploration, improvement, and joint construction over two years, which has formed AiNiee's relatively mature and complete AI translation system today.
Please respect the open-source spirit while using and learning, attribute the source project, and don't forget to give the project a star.

This AI translation tool is for personal legal use only. Any direct or indirect illegal profit-making activities using this tool are not within the scope of authorization and are not supported or endorsed.

* **`Community Groups`**: TG Group: https://t.me/+JVHbDSGo8SI2Njhl

---

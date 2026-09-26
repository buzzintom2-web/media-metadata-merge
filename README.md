# Media Metadata Merge for Windows

A simple desktop GUI for merging Google Photos `.supplemental-metadata.json` files into new image and video copies.

## Features

- Choose media, JSON, and output folders
- Match sidecars by filename
- Preserve original files
- Import capture date, creation date, title, GPS, and altitude
- Recover camera make/model/software from source EXIF or QuickTime metadata
- Optional image-to-JPEG conversion
- Remux iPhone MP4/MOV video/audio without re-encoding

## Build the Windows EXE

### Automatic build with GitHub Actions (recommended)

**You do not need to upload `ffmpeg.exe` or `exiftool.exe` to GitHub.** The workflow in `.github/workflows/build-windows.yml` installs both tools automatically on the temporary Windows build machine, bundles them into the finished app, and then removes the build machine.

Push this project to a GitHub repository. The workflow runs automatically on every push, builds the Windows portable application, and uploads `MediaMetadataMerge-windows-x64.zip` as a workflow artifact. In GitHub, open **Actions**, select the completed **Build Windows application** run, and download the artifact from the **Artifacts** section. No Python installation or local build is required.

After changing the workflow, download the artifact from the **newest successful run**. Do not reuse an artifact from an earlier run. Open the downloaded ZIP and confirm it contains `MediaMetadataMerge/tools/ffmpeg.exe` and `MediaMetadataMerge/tools/exiftool.exe` before launching the application.

The workflow can also be started manually with **Actions → Build Windows application → Run workflow**.

### Local build

1. Install **Python 3.11+ for Windows** from https://www.python.org/downloads/windows/ and select **Add Python to PATH**.
2. For a local build, install FFmpeg and ExifTool separately and put `ffmpeg.exe` and `exiftool.exe` in this project’s `tools` folder, or add both to Windows PATH. This step is **not needed** when using GitHub Actions.
3. Double-click `build_windows.bat`.
4. The portable application will be created at `dist\\MediaMetadataMerge\\MediaMetadataMerge.exe`.
5. Copy the whole `dist\\MediaMetadataMerge` folder to any Windows computer; no Python installation is needed to run the built app.

The build uses PyInstaller and has no Python package dependencies beyond the standard library/Tkinter.

## Use

1. Open the application.
2. Select the folder containing photos/videos.
3. Select the folder containing matching `.supplemental-metadata.json` files.
4. Select a new, empty output folder.
5. Optionally enable JPEG conversion.
6. Click **Merge Metadata**.

Only matching files are processed. A `0,0` JSON location is treated as missing. If an exact camera model is not present in the source media, the app does not invent one.

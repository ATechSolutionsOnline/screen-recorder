"""
build.py  --  One-click build: produces ScreenRecorderSetup.exe
Usage:  python build.py
Output: dist/ScreenRecorderSetup.exe
"""

import os
import sys
import shutil
import subprocess
import textwrap
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
APP_NAME     = "ScreenRecorder"
APP_DISPLAY  = "Screen Recorder"
APP_VERSION  = "1.0.0"
APP_PUBLISHER= "Screen Recorder"

BASE  = Path(__file__).parent.resolve()
DIST  = BASE / "dist"
BUILD = BASE / "_build_tmp"

# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(msg):
    print(f"\n{'='*56}\n  {msg}\n{'='*56}")


def run(cmd, check=True, **kw):
    cmd = [str(c) for c in cmd]
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, **kw)
    if check and r.returncode != 0:
        print(f"\nERROR: command failed (exit {r.returncode})")
        sys.exit(1)
    return r


def pip_install(pkg):
    run([sys.executable, "-m", "pip", "install", pkg, "-q"])


# ── Step 1: Prerequisites ──────────────────────────────────────────────────────

def ensure_icon():
    ico = BASE / "icon.ico"
    if not ico.exists():
        print("Generating icon.ico ...")
        sys.path.insert(0, str(BASE))
        from create_icon import generate
        generate(str(ico))
    print(f"Icon: {ico}")
    return ico


def find_ffmpeg():
    ff = shutil.which("ffmpeg")
    if ff:
        return Path(ff)
    lad = os.environ.get("LOCALAPPDATA", "")
    for exe in Path(lad).glob(
        "Microsoft/WinGet/Packages/Gyan.FFmpeg*/**/ffmpeg.exe"
    ):
        return exe
    return None


def ensure_pyinstaller():
    try:
        import PyInstaller
        print(f"PyInstaller {PyInstaller.__version__} found.")
        return
    except ImportError:
        pass
    print("Installing PyInstaller ...")
    pip_install("pyinstaller")


# ── Step 2: PyInstaller build ──────────────────────────────────────────────────

def build_exe(ffmpeg_path: Path, icon_path: Path) -> Path:
    banner("Step 2 — Building standalone exe (PyInstaller)")

    # Clean previous build
    if BUILD.exists():
        shutil.rmtree(BUILD)
    app_dist = DIST / APP_NAME
    if app_dist.exists():
        shutil.rmtree(app_dist)

    spec = textwrap.dedent(f"""\
        # -*- mode: python ; coding: utf-8 -*-
        a = Analysis(
            [r'{BASE / "main.py"}'],
            pathex=[r'{BASE}'],
            binaries=[
                (r'{ffmpeg_path}', '.'),
            ],
            datas=[
                (r'{icon_path}', '.'),
            ],
            hiddenimports=[
                'mss', 'mss.windows',
                'cv2',
                'numpy',
                'sounddevice', '_sounddevice_data',
                'scipy', 'scipy.io', 'scipy.io.wavfile',
                'scipy._lib', 'scipy._lib.messagestream',
                'PIL', 'PIL.Image', 'PIL.ImageDraw',
                'cffi', '_cffi_backend',
                'config', 'recorder', 'gui',
                'region_selector', 'create_icon',
            ],
            hookspath=[],
            runtime_hooks=[],
            excludes=[
                'matplotlib', 'pandas', 'IPython',
                'jupyter', 'notebook', 'pytest',
            ],
            noarchive=False,
        )
        pyz = PYZ(a.pure, a.zipped_data)
        exe = EXE(
            pyz, a.scripts, [],
            exclude_binaries=True,
            name='{APP_NAME}',
            debug=False,
            strip=False,
            upx=False,
            console=False,
            icon=r'{icon_path}',
        )
        coll = COLLECT(
            exe, a.binaries, a.zipfiles, a.datas,
            strip=False,
            upx=False,
            name='{APP_NAME}',
        )
    """)

    spec_path = BASE / f"{APP_NAME}.spec"
    spec_path.write_text(spec, encoding="utf-8")
    print(f"Spec written: {spec_path}")

    run([
        sys.executable, "-m", "PyInstaller",
        "--distpath", str(DIST),
        "--workpath",  str(BUILD),
        "--noconfirm",
        str(spec_path),
    ])

    exe_path = DIST / APP_NAME / f"{APP_NAME}.exe"
    if not exe_path.exists():
        print(f"ERROR: Expected exe not found: {exe_path}")
        sys.exit(1)

    size_mb = sum(f.stat().st_size for f in (DIST / APP_NAME).rglob("*") if f.is_file()) / 1e6
    print(f"\nBuild OK  —  {APP_NAME}/ folder  ({size_mb:.0f} MB)")
    return DIST / APP_NAME


# ── Step 3: Inno Setup installer ───────────────────────────────────────────────

INNO_CANDIDATES = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""),
                 "Programs", "Inno Setup 6", "ISCC.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""),
                 "Programs", "Inno Setup 5", "ISCC.exe"),
]


def find_inno():
    for p in INNO_CANDIDATES:
        if Path(p).exists():
            return Path(p)
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    return None


def install_inno():
    iscc = find_inno()
    if iscc:
        return iscc
    print("Installing Inno Setup via winget ...")
    run(["winget", "install", "--id", "JRSoftware.InnoSetup",
         "-e", "--silent", "--accept-package-agreements",
         "--accept-source-agreements"],
        check=False)
    return find_inno()


def create_installer(app_dir: Path, icon_path: Path) -> Path | None:
    banner("Step 3 — Creating Windows installer (Inno Setup)")

    iscc = install_inno()
    if not iscc:
        print("WARNING: Inno Setup not found — skipping installer.")
        print(f"Standalone exe: {app_dir / APP_NAME}.exe")
        return None

    iss_content = textwrap.dedent(f"""\
        [Setup]
        AppName={APP_DISPLAY}
        AppVersion={APP_VERSION}
        AppPublisher={APP_PUBLISHER}
        DefaultDirName={{autopf}}\\{APP_NAME}
        DefaultGroupName={APP_DISPLAY}
        OutputDir={DIST}
        OutputBaseFilename=ScreenRecorderSetup
        SetupIconFile={icon_path}
        Compression=lzma2
        SolidCompression=yes
        WizardStyle=modern
        PrivilegesRequired=lowest
        ArchitecturesInstallIn64BitMode=x64compatible
        UninstallDisplayIcon={{app}}\\{APP_NAME}.exe
        DisableProgramGroupPage=yes

        [Languages]
        Name: "english"; MessagesFile: "compiler:Default.isl"

        [Tasks]
        Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; \\
            GroupDescription: "{{cm:AdditionalIcons}}"

        [Files]
        Source: "{app_dir}\\*"; DestDir: "{{app}}"; \\
            Flags: ignoreversion recursesubdirs createallsubdirs

        [Icons]
        Name: "{{group}}\\{APP_DISPLAY}"; Filename: "{{app}}\\{APP_NAME}.exe"
        Name: "{{autodesktop}}\\{APP_DISPLAY}"; Filename: "{{app}}\\{APP_NAME}.exe"; \\
            Tasks: desktopicon

        [Run]
        Filename: "{{app}}\\{APP_NAME}.exe"; \\
            Description: "{{cm:LaunchProgram,{APP_DISPLAY}}}"; \\
            Flags: nowait postinstall skipifsilent
    """)

    iss_path = BASE / "installer.iss"
    iss_path.write_text(iss_content, encoding="utf-8")
    print(f"Inno script: {iss_path}")

    run([str(iscc), str(iss_path)])

    out = DIST / "ScreenRecorderSetup.exe"
    if out.exists():
        size_mb = out.stat().st_size / 1e6
        banner(f"SUCCESS  —  Installer ready!")
        print(f"  File : {out}")
        print(f"  Size : {size_mb:.1f} MB")
        print(f"\n  Copy ScreenRecorderSetup.exe to any Windows PC and run it.")
        print(f"  No Python, no FFmpeg, no extras needed on the target machine.")
        return out

    print("ERROR: Installer exe not found after build.")
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    banner(f"Screen Recorder Build  v{APP_VERSION}")

    # Step 1
    banner("Step 1 — Checking prerequisites")
    icon_path = ensure_icon()

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("ERROR: ffmpeg.exe not found.")
        print("Run install.bat first, or install FFmpeg and add it to PATH.")
        sys.exit(1)
    print(f"FFmpeg : {ffmpeg}")

    ensure_pyinstaller()

    # Step 2
    app_dir = build_exe(ffmpeg, icon_path)

    # Step 3
    installer = create_installer(app_dir, icon_path)

    if installer:
        # Open dist folder
        os.startfile(str(DIST))
    else:
        os.startfile(str(app_dir))


if __name__ == "__main__":
    main()

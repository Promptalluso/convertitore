"""Build a self-contained test package on its target operating system."""

import hashlib
import importlib.metadata
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PACKAGE = ROOT / "packaging"
sys.path.insert(0, str(ROOT / "src"))
from convertitore.version import VERSION  # noqa: E402

DEPENDENCIES = ("Pillow", "PySide6-Essentials", "shiboken6", "pypdf", "pypdfium2", "imageio-ffmpeg", "rapidocr", "onnxruntime", "reportlab", "pyinstaller")


def copy_notices(bundle: Path) -> None:
    resources = bundle / "Contents" / "Resources" if sys.platform == "darwin" else bundle
    licenses = resources / "licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", licenses / "Convertitore-GPL-3.0.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", licenses / "THIRD_PARTY_NOTICES.md")
    shutil.copytree(PACKAGE / "license_texts", licenses, dirs_exist_ok=True)
    shutil.copy2(ROOT / "README.md", resources / "START-HERE.md")
    source = resources / "source"
    shutil.copytree(ROOT / "src", source / "src", ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    for name in ("pyproject.toml", "requirements.txt", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, source / name)
    (source / "packaging").mkdir(exist_ok=True)
    shutil.copy2(PACKAGE / "native_glass.mm", source / "packaging" / "native_glass.mm")
    versions = {}
    for name in DEPENDENCIES:
        distribution = importlib.metadata.distribution(name)
        versions[name] = distribution.version
        for entry in distribution.files or ():
            if "license" not in str(entry).lower() and "copying" not in str(entry).lower():
                continue
            original = Path(distribution.locate_file(entry))
            if original.is_file():
                target = licenses / name / str(entry).replace("..", "_")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, target)
    (resources / "dependencies.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")


def main() -> None:
    if sys.platform not in ("darwin", "win32"):
        raise SystemExit("Build only on macOS or Windows.")
    icon = PACKAGE / ("icon.icns" if sys.platform == "darwin" else "icon.ico")
    if not icon.is_file():
        subprocess.run([sys.executable, str(PACKAGE / "make_icon.py")], check=True)
    import imageio_ffmpeg
    ffmpeg_source = Path(imageio_ffmpeg.get_ffmpeg_exe())
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--windowed", "--onedir", "--name", "Convertitore",
               "--paths", str(ROOT / "src"), "--collect-data", "rapidocr",
               "--icon", str(icon), str(PACKAGE / "entry.py")]
    target_arch = os.environ.get("CONVERTITORE_TARGET_ARCH")
    if target_arch:
        if sys.platform != "darwin" or target_arch not in ("arm64", "x86_64", "universal2"):
            raise SystemExit("Invalid CONVERTITORE_TARGET_ARCH.")
        command.extend(["--target-arch", target_arch])
    if sys.platform == "darwin":
        command.extend(["--osx-bundle-identifier", "dev.convertitore.suite"])
    subprocess.run(command, cwd=ROOT, check=True)
    DIST.mkdir(exist_ok=True)
    if sys.platform == "darwin":
        bundle = DIST / "Convertitore.app"
        copy_notices(bundle)
        plist_path = bundle / "Contents" / "Info.plist"
        info_plist = plistlib.loads(plist_path.read_bytes())
        info_plist["CFBundleDisplayName"] = f"Convertitore v{VERSION}"
        info_plist["CFBundleShortVersionString"] = VERSION
        info_plist["CFBundleVersion"] = VERSION
        plist_path.write_bytes(plistlib.dumps(info_plist))
        shutil.copy2(ffmpeg_source, bundle / "Contents" / "Resources" / "ffmpeg")
        bridge = bundle / "Contents" / "Resources" / "native_glass.dylib"
        subprocess.run(["clang++", "-x", "objective-c++", "-dynamiclib", "-fobjc-arc",
                        "-framework", "AppKit", str(PACKAGE / "native_glass.mm"),
                        "-o", str(bridge)], check=True)
        # Adding license/source resources changes the PyInstaller ad-hoc seal.
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(bundle)], check=True)
        subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
        binary = bundle / "Contents" / "MacOS" / "Convertitore"
        info = subprocess.check_output(["lipo", "-info", str(binary)], text=True)
        print(info.strip())
        if target_arch == "universal2" and not all(arch in info for arch in ("x86_64", "arm64")):
            raise RuntimeError("Mac build is not universal2.")
        archive = DIST / "Convertitore-macOS-dev.dmg"
        # The Applications shortcut lets people install by dragging inside the disk window.
        staging = DIST / "dmg"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        subprocess.run(["ditto", str(bundle), str(staging / "Convertitore.app")], check=True)
        (staging / "Applicazioni").symlink_to("/Applications")
        subprocess.run(["hdiutil", "create", "-volname", f"Convertitore v{VERSION}", "-srcfolder",
                        str(staging), "-ov", "-format", "UDZO", str(archive)], check=True)
        shutil.rmtree(staging)
    else:
        bundle = DIST / "Convertitore"
        copy_notices(bundle)
        shutil.copy2(ffmpeg_source, bundle / "ffmpeg.exe")
        archive = Path(shutil.make_archive(str(DIST / "Convertitore-Windows-dev"), "zip",
                                           root_dir=DIST, base_dir="Convertitore"))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8")
    print(archive)


if __name__ == "__main__":
    main()

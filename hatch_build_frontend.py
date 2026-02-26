import os
import subprocess
import shutil
from hatchling.builders.hooks.plugin.interface import BuildHookInterface  # pyright: ignore[reportMissingImports]


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        """This runs right before the wheel is built."""
        print("🔨 Starting automatic frontend build...")

        root_dir = os.path.dirname(os.path.abspath(__file__))
        frontend_dir = os.path.join(root_dir, "frontend")
        ui_dest_dir = os.path.join(root_dir, "src", "hestia", "ui")
        is_windows = os.name == "nt"
        has_lockfile = os.path.exists(os.path.join(frontend_dir, "package-lock.json"))

        # 1. Check for the Docker bypass variable
        if os.environ.get("SKIP_FRONTEND_BUILD") == "1":
            print("⏭️  SKIP_FRONTEND_BUILD is set. Skipping npm build.")
            return

        # 2. Check if npm exists on the system
        if shutil.which("npm") is None:
            # If npm is missing, but the UI folder has files, assume it's a source distribution and proceed safely
            if os.path.exists(ui_dest_dir) and os.listdir(ui_dest_dir):
                print("⚠️  npm not found, but UI files exist. Proceeding with existing UI.")
                return
            else:
                raise RuntimeError("❌ npm is not installed, and no pre-built UI files were found!")

        # 1. Run npm dependency install and build
        try:
            install_cmd = ["npm", "ci"] if has_lockfile else ["npm", "install"]
            try:
                subprocess.run(install_cmd, cwd=frontend_dir, check=True, shell=is_windows)
            except subprocess.CalledProcessError:
                # Some environments fail strict peer resolution (ERESOLVE).
                # Retry with legacy peer deps so editable/wheel builds can proceed.
                legacy_cmd = install_cmd + ["--legacy-peer-deps"]
                print("⚠️  npm dependency resolution failed; retrying with --legacy-peer-deps...")
                subprocess.run(legacy_cmd, cwd=frontend_dir, check=True, shell=is_windows)

            subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True, shell=is_windows)
        except subprocess.CalledProcessError as e:
            print(f"❌ Frontend build failed: {e}")
            raise e

        # 2. Clean the target directory
        if os.path.exists(ui_dest_dir):
            shutil.rmtree(ui_dest_dir)
        os.makedirs(ui_dest_dir, exist_ok=True)

        # 3. Copy the compiled files over
        dist_dir = os.path.join(frontend_dir, "dist")
        for item in os.listdir(dist_dir):
            s = os.path.join(dist_dir, item)
            d = os.path.join(ui_dest_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        print("✅ Frontend successfully injected into Python package.")

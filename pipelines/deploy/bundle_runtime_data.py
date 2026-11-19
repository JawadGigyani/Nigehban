"""Bundle the runtime data (see backend/app/runtime_data.py) and optionally upload it.

    python -m pipelines.deploy.bundle_runtime_data                      # build data/bundle/, show size
    python -m pipelines.deploy.bundle_runtime_data --upload user/nigehban-runtime   # + upload (needs HF_TOKEN)

The bundle never includes private data (PDMA reports, extractions, events, labels); a check
refuses to build if any such path slips in.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from backend.app.config import get_settings
from backend.app.runtime_data import RUNTIME_FILES

FORBIDDEN = ("raw/pdma", "interim/pdma", "events/", "risk_oof", "spot_check")


def build(data_dir: Path, out: Path) -> int:
    if out.exists():
        shutil.rmtree(out)
    total = 0
    for rel in RUNTIME_FILES:
        if any(f in rel for f in FORBIDDEN):
            raise SystemExit(f"refusing to bundle private path {rel}")
        src = data_dir / rel
        if rel.endswith("/"):
            for f in src.rglob("*"):
                if f.is_file() and not f.name.startswith("_pacer") and f.suffix != ".tmp":
                    dst = out / rel / f.relative_to(src)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dst)
                    total += f.stat().st_size
        else:
            if not src.is_file():
                raise SystemExit(f"missing {src}; build it first")
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            total += src.stat().st_size
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", help="Hugging Face dataset repo id, e.g. yourname/nigehban-runtime")
    args = parser.parse_args()
    data = get_settings().data_dir
    out = data / "bundle"
    size = build(data, out)
    files = sum(1 for f in out.rglob("*") if f.is_file())
    print(f"bundle: {files} files, {size / 1e6:.0f} MB -> {out}")
    if args.upload:
        from huggingface_hub import HfApi

        api = HfApi(token=os.environ.get("HF_TOKEN"))
        api.create_repo(args.upload, repo_type="dataset", private=True, exist_ok=True)
        api.upload_large_folder(repo_id=args.upload, repo_type="dataset", folder_path=str(out))
        print(f"uploaded to https://huggingface.co/datasets/{args.upload} (private)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

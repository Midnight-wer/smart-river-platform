"""获取/校验河道塑料瓶数据集。

- 自动下载：GitHub 上可直接下载的部分（如 SSZ5 的 labels.zip、仓库归档）
- 人工下载：网盘/Google Drive 等无法脚本化的部分，脚本给出指引并校验本地是否就绪

用法：
    python scripts/fetch_datasets.py            # 校验所有源 + 自动下载可下载部分
    python scripts/fetch_datasets.py --check    # 仅校验，不下载
"""
from __future__ import annotations

import argparse
import io
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    RAW_DIR,
    SOURCES_KEY,
    ROOT,
    alias_set,
    is_plastic_bottle,
    iter_pairs,
    load_label_db,
    parse_voc_xml,
    parse_yolo_txt,
)

CODELOAD = "https://codeload.github.com/{repo}/zip/refs/heads/{branch}"
BRANCHES = ("main", "master")


def http_get(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "river-admin-ai-training"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download_repo_archive(repo: str, dest: Path) -> bool:
    """下载 GitHub 仓库归档并解压到目标目录。"""
    for branch in BRANCHES:
        try:
            payload = http_get(CODELOAD.format(repo=repo, branch=branch))
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"    ! 拉取 {repo}@{branch} 失败: {error}")
            continue
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            archive.extractall(dest)
        print(f"    + 已下载仓库归档 {repo}@{branch} -> {dest}")
        return True
    return False


def clone_github_images(repo: str, dest: Path) -> bool:
    """拉取 GitHub 仓库的图片分支（SSZ5 的图片位于 images 分支，且为 Git LFS 对象）。

    git-lfs 的 smudge 过滤器会在 clone 时自动下载真实内容；未安装 git-lfs 时只会得到指针文件，
    因此这里对 zip 大小做校验。
    """
    import subprocess

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", "images", f"https://github.com/{repo}.git", str(dest)],
            check=True, capture_output=True, timeout=3600,
        )
    except FileNotFoundError:
        print("    ! 未安装 git，无法自动拉取图片分支")
        return False
    except subprocess.CalledProcessError as error:
        print(f"    ! git clone 失败: {error.stderr.decode('utf-8', 'ignore')[:200]}")
        return False

    zips = list(dest.glob("image_*.zip"))
    pointers = [z for z in zips if z.stat().st_size < 4096]
    if pointers:
        print(f"    ! 检测到 {len(pointers)} 个 LFS 指针文件，请确认已安装 git-lfs 后执行: git lfs pull")
        return False
    total = sum(z.stat().st_size for z in zips)
    print(f"    + 已拉取 {len(zips)} 个图片压缩包（{total / 1024 / 1024:.0f} MB）")
    return True


def extract_archives(dest: Path, target_subdir: str = "images") -> int:
    """解压仓库内所有 image_*.zip 到 images/ 目录。"""
    target = dest / target_subdir
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for archive_path in sorted(dest.glob("image_*.zip")):
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target)
        count += 1
    if count:
        print(f"    + 解压 {count} 个压缩包 -> {target}")
    return count


def fetch_labels_archive(dest: Path) -> int:
    """解压仓库内 labels.zip 标注包。"""
    count = 0
    for archive_path in list(dest.rglob("labels*.zip")):
        target = archive_path.parent / f"{archive_path.stem}_extracted"
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target)
        count += 1
        print(f"    + 解压 {archive_path.name} -> {target}")
    return count


def fetch_labels_via_git(repo_dir: Path, out_dir: Path) -> bool:
    """从仓库的 master 分支取出 labels.zip（LFS 内容经 smudge 自动落地）并解压。"""
    import subprocess

    try:
        subprocess.run(
            ["git", "-C", str(repo_dir), "fetch", "origin", "master", "--depth", "1"],
            check=True, capture_output=True, timeout=600,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "checkout", "FETCH_HEAD", "--", "labels.zip"],
            check=True, capture_output=True, timeout=600,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"    ! 获取 labels.zip 失败: {error}")
        return False
    archive = repo_dir / "labels.zip"
    if not archive.exists() or archive.stat().st_size < 1024:
        print("    ! labels.zip 缺失或为 LFS 指针，请确认已安装 git-lfs")
        return False
    target = out_dir / "labels"
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(target)
    print(f"    + 标注已解压 -> {target}")
    return True


def inspect_dataset(dataset_dir: Path) -> dict:
    """统计数据集内的样本数与塑料瓶目标数（支持 YOLO txt 与 Pascal VOC xml）。"""
    label_db = load_label_db()
    aliases = alias_set(label_db)
    total = 0
    bottles = 0
    for image, label, class_names in iter_pairs(dataset_dir):
        total += 1
        if label.suffix.lower() == ".xml":
            boxes = parse_voc_xml(label, class_names)
        else:
            boxes = parse_yolo_txt(label, class_names)
        for box in boxes:
            if is_plastic_bottle(box.cls_name, aliases):
                bottles += 1
    return {"samples": total, "bottles": bottles}


def main() -> int:
    parser = argparse.ArgumentParser(description="获取/校验河道塑料瓶数据集")
    parser.add_argument("--check", action="store_true", help="仅校验，不执行下载")
    args = parser.parse_args()

    label_db = load_label_db()
    sources = label_db[SOURCES_KEY]
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"数据集根目录: {RAW_DIR}")
    ready_count = 0
    for source in sources:
        sid = source["id"]
        target = RAW_DIR / sid
        print(f"\n[{sid}] {source['name']}")

        if not args.check and source.get("repo"):
            if sid == "ssz5-plastic-bottles-in-water":
                # SSZ5：图片在 images 分支（Git LFS 压缩包），标注在 master 分支
                if not (target / "images").exists():
                    if clone_github_images(source["repo"], target):
                        extract_archives(target, "images")
                if not (target / "labels").exists():
                    fetch_labels_via_git(target, target)
            elif not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                if download_repo_archive(source["repo"], target):
                    fetch_labels_archive(target)
                else:
                    print(f"    ! 仓库 {source['repo']} 无法自动下载，需人工处理")

        if not target.exists():
            print(f"    - 待人工下载: {source.get('manual_note', '（无说明）')}")
            continue

        stats = inspect_dataset(target)
        if stats["samples"] == 0:
            print(f"    - 目录已存在但未发现 images/labels 配对样本")
            print(f"      待人工下载: {source.get('manual_note', '（无说明）')}")
            continue
        ready_count += 1
        print(f"    ✓ 已就绪: 样本 {stats['samples']} 张，塑料瓶目标 {stats['bottles']} 个")

    print(f"\n就绪数据集: {ready_count}/{len(sources)}")
    print("下一步: python scripts/clean_dataset.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

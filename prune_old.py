#!/usr/bin/env python3
"""按保留天数清理过期发布记录，释放本地磁盘。

只清理能从文件名解析出日期的带日期产物（绝不动无日期的文件）：
  - data_YYYY-MM-DD.json
  - trending_YYYY-MM-DD.json
  - readme_YYYY-MM-DD.json
  - run_log_YYYY-MM-DD.json
  - output/YYYY-MM-DD/        （每日生成的 html/png/copy）
  - output_weekly/YYYY-MM-DD/ （周榜，按同一规则清理）

规则：保留最近 RETENTION_DAYS 天（含今天），其余删除。
     例：RETENTION_DAYS=14 -> 保留 today-13 .. today，删 <= today-14。

用法:
  python prune_old.py [--days 14] [--dry-run]
"""
import argparse
import datetime
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# (glob 模式, 仅目录) —— 只处理带日期的子项
TARGETS = [
    ("data_*-*.json", False),
    ("trending_*-*.json", False),
    ("readme_*-*.json", False),
    ("run_log_*-*.json", False),
    ("output/*", True),
    ("output_weekly/*", True),
]

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _size(p: Path) -> int:
    if not p.exists():
        return 0
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    return p.stat().st_size


def prune(retention_days: int = 14, dry_run: bool = False, root: Path = ROOT):
    """删除日期早于保留线的带日期产物。返回 (cutoff, [(relpath, date), ...], freed_bytes)。"""
    today = datetime.date.today()
    # 含今天共 retention_days 天 -> 保留 >= today-(retention_days-1)
    cutoff = today - datetime.timedelta(days=retention_days - 1)
    removed = []
    freed = 0
    for pat, _is_dir in TARGETS:
        for p in sorted(root.glob(pat)):
            m = DATE_RE.search(p.name)
            if not m:
                continue
            try:
                d = datetime.date.fromisoformat(m.group(1))
            except ValueError:
                continue
            if d < cutoff:
                size = _size(p)
                freed += size
                removed.append((str(p.relative_to(root)), d.isoformat()))
                if not dry_run:
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
    return cutoff, removed, freed


def main():
    ap = argparse.ArgumentParser(description="清理过期发布记录（保留最近 N 天）")
    ap.add_argument("--days", type=int, default=14, help="保留天数，默认 14")
    ap.add_argument("--dry-run", action="store_true", help="只预览不删除")
    args = ap.parse_args()

    cutoff, removed, freed = prune(args.days, args.dry_run)
    if args.dry_run:
        print(f"[预览] 保留线: >= {cutoff}（最近 {args.days} 天）；以下将在真实运行时删除：")
    else:
        print(f"[执行] 保留线: >= {cutoff}（最近 {args.days} 天）")

    if not removed:
        print("无需清理，全部已在保留期内。")
    else:
        print(f"共 {'将' if args.dry_run else '已'}删除 {len(removed)} 项，"
              f"释放约 {freed / 1024 / 1024:.1f} MB：")
        for rel, d in removed:
            print(f"  - {rel}  ({d})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

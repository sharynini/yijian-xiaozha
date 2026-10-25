# -*- coding: utf-8 -*-
"""
一次性清理：name 为空、且没有任何 wear_log 引用的 outfit。

关联表 outfit_item 会随 MySQL ON DELETE CASCADE 一起删掉。
被日记引用的 outfit 一律保留（含已软删的 wear_log）。

默认 dry-run，只打印数量。加 --apply 才真正删除。

用法（在 server/ 目录）：
    python scripts/cleanup_orphan_outfits.py
    python scripts/cleanup_orphan_outfits.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from dotenv import load_dotenv

load_dotenv(SERVER_ROOT / '.env', override=True)

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.outfit import Outfit, OutfitItem  # noqa: E402
from app.models.wear_log import WearLog  # noqa: E402


def _orphan_outfit_ids():
    """name 为 NULL/空串，且不存在 outfit_id 指向它的 wear_log。"""
    referenced = (
        db.session.query(WearLog.outfit_id)
        .filter(WearLog.outfit_id.isnot(None))
    )
    rows = (
        db.session.query(Outfit.id)
        .filter(
            db.or_(Outfit.name.is_(None), Outfit.name == ''),
            ~Outfit.id.in_(referenced),
        )
        .all()
    )
    return [oid for (oid,) in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description='清理未被日记引用的无名 outfit')
    parser.add_argument(
        '--apply',
        action='store_true',
        help='真正删除；不加此参数只统计（dry-run）',
    )
    args = parser.parse_args()

    app = create_app('default')
    with app.app_context():
        ids = _orphan_outfit_ids()
        outfit_count = len(ids)
        item_count = 0
        if ids:
            item_count = (
                db.session.query(OutfitItem.id)
                .filter(OutfitItem.outfit_id.in_(ids))
                .count()
            )

        mode = 'APPLY' if args.apply else 'DRY-RUN'
        print(f'[{mode}] 将删除 outfit 行数: {outfit_count}')
        print(f'[{mode}] 将级联删除 outfit_item 行数: {item_count}')

        if not args.apply:
            print('未加 --apply，未执行删除。')
            return 0

        if outfit_count == 0:
            print('没有可删除的行。')
            return 0

        deleted = (
            db.session.query(Outfit)
            .filter(Outfit.id.in_(ids))
            .delete(synchronize_session=False)
        )
        db.session.commit()
        print(f'已删除 outfit 行数: {deleted}')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())

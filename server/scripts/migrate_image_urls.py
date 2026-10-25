# -*- coding: utf-8 -*-
"""
一次性迁移：把库里已存的「本站图片完整地址」改成相对路径 /uploads/xxx。

涉及字段：
    item.image_url
    wear_log.photo_url
    wear_log.items_snapshot[*].image_url
    user.avatar

哪些地址会被改：路径以 /uploads/ 开头，且主机是 localhost / 回环 / 局域网 IP，
或等于 PUBLIC_BASE_URL 的主机，或通过 --host 额外指定的主机。外部链接不动。

默认 dry-run，只打印将要修改的数量和示例；加 --apply 才真正写库。
执行前请先备份数据库。

用法（在 server/ 目录）：
    python scripts/migrate_image_urls.py
    python scripts/migrate_image_urls.py --host my-old-domain.com
    python scripts/migrate_image_urls.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from dotenv import load_dotenv

load_dotenv(SERVER_ROOT / '.env', override=True)

import os  # noqa: E402

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app import create_app  # noqa: E402
from app.common.media import to_storage_path  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.item import Item  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.wear_log import WearLog  # noqa: E402

SAMPLE_LIMIT = 3


def _convert(value, hosts):
    new = to_storage_path(value, extra_hosts=hosts)
    return new, (isinstance(value, str) and new != value)


def _migrate_column(model, column: str, hosts, samples: list) -> int:
    """处理普通字符串字段，返回变更行数（包含软删除的数据）"""
    changed = 0
    for row in model.query.filter(getattr(model, column).isnot(None)).all():
        old = getattr(row, column)
        new, is_changed = _convert(old, hosts)
        if is_changed:
            setattr(row, column, new)
            changed += 1
            if len(samples) < SAMPLE_LIMIT:
                samples.append(f'{model.__tablename__}#{row.id}.{column}: {old} → {new}')
    return changed


def _migrate_snapshots(hosts, samples: list) -> int:
    """处理 wear_log.items_snapshot 里每件衣物的 image_url"""
    changed = 0
    for log in WearLog.query.filter(WearLog.items_snapshot.isnot(None)).all():
        snapshot = log.items_snapshot
        if not isinstance(snapshot, list):
            continue
        new_snapshot, row_changed = [], False
        for entry in snapshot:
            if isinstance(entry, dict):
                new, is_changed = _convert(entry.get('image_url'), hosts)
                if is_changed:
                    if len(samples) < SAMPLE_LIMIT:
                        samples.append(f'wear_log#{log.id}.items_snapshot: {entry.get("image_url")} → {new}')
                    entry = {**entry, 'image_url': new}
                    row_changed = True
            new_snapshot.append(entry)
        if row_changed:
            log.items_snapshot = new_snapshot
            flag_modified(log, 'items_snapshot')
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description='把本站图片完整地址迁移为相对路径')
    parser.add_argument('--apply', action='store_true', help='真正写库（默认只预览）')
    parser.add_argument('--host', action='append', default=[],
                        help='额外视为本站的主机名（可多次传入），如旧域名')
    args = parser.parse_args()

    app = create_app(os.getenv('FLASK_CONFIG', 'default'))
    with app.app_context():
        samples: list = []
        stats = {
            'item.image_url': _migrate_column(Item, 'image_url', args.host, samples),
            'wear_log.photo_url': _migrate_column(WearLog, 'photo_url', args.host, samples),
            'wear_log.items_snapshot': _migrate_snapshots(args.host, samples),
            'user.avatar': _migrate_column(User, 'avatar', args.host, samples),
        }

        for name, count in stats.items():
            print(f'{name:<26} 待修改 {count} 行')
        if samples:
            print('\n示例：')
            for line in samples:
                print('  ' + line)

        total = sum(stats.values())
        if not args.apply:
            db.session.rollback()
            print(f'\n[dry-run] 共 {total} 行待修改，未写库。确认无误后加 --apply 执行。')
            return 0

        db.session.commit()
        print(f'\n[apply] 已修改 {total} 行。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

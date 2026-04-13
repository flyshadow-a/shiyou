from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from shiyou_db.config import load_settings
    from shiyou_db.database import Base, build_engine
    from shiyou_db.service import FileMetadataService
else:
    from .config import load_settings
    from .database import Base, build_engine
    from .service import FileMetadataService


def main() -> int:
    settings = load_settings()
    engine = build_engine(settings)
    Base.metadata.create_all(engine)
    service = FileMetadataService(settings)
    service.seed_file_types()
    print("Database tables created and file types seeded.")
    print(f"Storage root: {settings.storage_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

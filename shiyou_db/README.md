# shiyou_db

MySQL metadata module for shiyou file upload/download.

Architecture:
- MySQL stores file metadata only.
- Real files stay on disk under a configurable storage root.
- The package now lives inside the main `shiyou` repo under `shiyou_db/`.
- Local runtime still uses `shiyou_db/db_config.json`; this file is ignored by Git.
- Existing local storage can continue pointing at `D:/pyproject/shiyou_db/shiyou_file_storage` to avoid breaking old records.

Recommended tables:
1. file_types
   - id
   - code
   - name
   - description
   - sort_order
   - is_active
   - created_at
   - updated_at

2. file_records
   - id
   - original_name
   - stored_name
   - file_ext
   - file_type_id
   - module_code
   - logical_path
   - facility_code
   - storage_path
   - category_name
   - work_condition
   - file_size
   - file_hash
   - source_modified_at
   - uploaded_at
   - updated_at
   - remark
   - is_deleted

Why fields beyond name/type/path/mtime are needed:
- original_name: user-facing download name
- stored_name: collision-free physical name
- module_code + logical_path: maps current UI tree and page structure
- facility_code: separates platform/project records
- file_size + file_hash: integrity and duplicate detection
- uploaded_at/updated_at: traceability
- is_deleted: soft delete support

Quick start:
1. Copy `db_config.example.json` to `db_config.json` and fill MySQL connection.
2. Run: python -m shiyou_db.init_db
3. Optional legacy migration: python -m shiyou_db.migrate_uploads --source-root D:/pyproject/shiyou/upload

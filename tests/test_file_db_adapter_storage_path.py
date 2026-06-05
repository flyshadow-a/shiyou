import json

from services.file_db_adapter import resolve_storage_path
from shiyou_db.config import load_settings
from shiyou_db.storage_share import unc_share_root


def test_resolve_storage_path_maps_legacy_storage_root(tmp_path):
    config_path = tmp_path / "db_config.json"
    config_path.write_text(
        json.dumps({"storage_root": r"\\fileserver\shiyou_file_storage"}),
        encoding="utf-8",
    )
    row = {
        "storage_path": r"D:\shiyou_file_storage\model_files\WC19-1D\current\sacinp",
        "module_code": "model_files",
        "logical_path": "WC19-1D/current",
        "stored_name": "sacinp",
    }

    resolved = resolve_storage_path(row, config_path=str(config_path)).replace("\\", "/")

    assert "D:" not in resolved
    assert resolved.endswith("/shiyou_file_storage/model_files/WC19-1D/current/sacinp")


def test_load_settings_reads_storage_share_credentials(tmp_path):
    config_path = tmp_path / "db_config.json"
    config_path.write_text(
        json.dumps(
            {
                "database": {
                    "host": "127.0.0.1",
                    "port": 3306,
                    "user": "u",
                    "password": "p",
                    "database": "d",
                },
                "storage_root": r"\\fileserver\shiyou_file_storage",
                "storage_share": {
                    "auto_connect": True,
                    "domain": "fileserver",
                    "username": "shiyou_client",
                    "password": "secret",
                    "force_reconnect": True,
                },
            }
        ),
        encoding="utf-8",
    )

    settings = load_settings(str(config_path))

    assert settings.storage_share.auto_connect is True
    assert settings.storage_share.username == r"fileserver\shiyou_client"
    assert settings.storage_share.password == "secret"
    assert settings.storage_share.force_reconnect is True


def test_unc_share_root_returns_server_and_share():
    assert (
        unc_share_root(r"\\fileserver\shiyou_file_storage\model_files\a.txt")
        == r"\\fileserver\shiyou_file_storage"
    )

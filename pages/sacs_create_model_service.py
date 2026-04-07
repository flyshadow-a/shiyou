# -*- coding: utf-8 -*-
from __future__ import annotations

from pages.sacs_wellslot_service import generate_wellslot_to_db
from pages.sacs_riser_service import generate_riser_to_db
from pages.sacs_topside_service import transform_topside_weights_to_db
from pages.sacs_export_service import export_model_bundle


def create_new_model_files(mysql_url: str, job_name: str, overwrite_job: bool = True, generate_bat: bool = False) -> dict:
    result_wellslot = generate_wellslot_to_db(
        mysql_url=mysql_url,
        job_name=job_name,
        overwrite_job=overwrite_job,
    )

    result_riser = generate_riser_to_db(
        mysql_url=mysql_url,
        job_name=job_name,
        overwrite_job=overwrite_job,
    )

    result_topside = transform_topside_weights_to_db(
        mysql_url=mysql_url,
        job_name=job_name,
        overwrite_job=overwrite_job,
    )

    result_export = export_model_bundle(
        mysql_url=mysql_url,
        job_name=job_name,
        generate_bat_flag=generate_bat,
    )

    return {
        "job_name": job_name,
        "wellslot": result_wellslot,
        "riser": result_riser,
        "topside": result_topside,
        "export": result_export,
    }
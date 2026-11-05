import inspect
import os
import socket
from collections.abc import Mapping
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snakemake.iocontainers import snakemake  # noqa: TC004

CALWEBB_ALIAS_PREFIX = "calwebb_"


def has_network_access(host="8.8.8.8", port=443, timeout=3):
    """Check network access before importing the JWST pipeline."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return True
    except (TimeoutError, OSError):
        return False


def pipeline_options(stage_name):
    jwst_config = snakemake.config.get("jwst", {})
    if not isinstance(jwst_config, Mapping):
        raise TypeError("JWST configuration jwst must be a mapping.")

    options = jwst_config.get(stage_name, {})

    if not isinstance(options, Mapping):
        raise TypeError(
            f"JWST stage configuration jwst.{stage_name} must be a mapping."
        )

    return dict(options)


def stage_id(pipeline_class):
    alias = pipeline_class.class_alias
    if not isinstance(alias, str) or not alias.startswith(CALWEBB_ALIAS_PREFIX):
        raise ValueError(
            f"JWST class {pipeline_class.__name__} has invalid class alias {alias!r}."
        )
    return alias.removeprefix(CALWEBB_ALIAS_PREFIX)


def available_stages():
    from jwst import pipeline, stpipe
    from jwst.wfs_combine.wfs_combine_step import WfsCombineStep
    from jwst_kpi import Kpi3Pipeline

    stages = {
        stage_id(pipeline_class): pipeline_class
        for _, pipeline_class in inspect.getmembers(pipeline, inspect.isclass)
        if issubclass(pipeline_class, stpipe.Pipeline)
        and pipeline_class is not stpipe.Pipeline
    }
    stages[stage_id(WfsCombineStep)] = WfsCombineStep
    stages["kpi3"] = Kpi3Pipeline
    return stages


def main(stage_name, input_file, output_dir, options):
    if not has_network_access():
        os.environ["CRDS_SERVER_URL"] = "https://jwst-serverless.stsci.edu"
        os.environ["STPIPE_DISABLE_CRDS_STEPPARS"] = "True"

    stages = available_stages()
    try:
        pipeline_class = stages[stage_name]
    except KeyError as error:
        supported_stages = ", ".join(sorted(stages))
        raise ValueError(
            f"Unsupported JWST stage {stage_name!r}. Expected one of: {supported_stages}."
        ) from error

    options.setdefault("save_results", True)
    pipeline_class.call(input_file, output_dir=str(output_dir), **options)


def run():
    stage_name = snakemake.params["stage_name"]
    main(
        stage_name,
        snakemake.input[0],
        Path(snakemake.output[0]).parent,
        pipeline_options(stage_name),
    )


if snakemake.log:
    log_path = Path(snakemake.log[0])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        log_path.open("w") as log_file,
        redirect_stdout(log_file),
        redirect_stderr(log_file),
    ):
        run()
else:
    run()

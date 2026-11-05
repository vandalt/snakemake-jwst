import importlib
import os
import socket
from collections.abc import Mapping
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snakemake.iocontainers import snakemake  # noqa: TC004

STAGE_IMPORTS = {
    "detector1": ("jwst.pipeline", "Detector1Pipeline"),
    "image2": ("jwst.pipeline", "Image2Pipeline"),
    "image3": ("jwst.pipeline", "Image3Pipeline"),
    "kpi3": ("jwst_kpi", "Kpi3Pipeline"),
}


def has_network_access(host="8.8.8.8", port=443, timeout=3):
    """Check network access before importing the JWST pipeline."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return True
    except (TimeoutError, OSError):
        return False


def pipeline_options(stage_name):
    if stage_name not in STAGE_IMPORTS:
        supported_stages = ", ".join(sorted(STAGE_IMPORTS))
        raise ValueError(
            f"Unsupported JWST stage {stage_name!r}. Expected one of: {supported_stages}."
        )

    try:
        options = snakemake.config["jwst"][stage_name]
    except KeyError as error:
        raise ValueError(
            f"Missing configuration for JWST stage {stage_name!r} at jwst.{stage_name}."
        ) from error

    if not isinstance(options, Mapping):
        raise TypeError(
            f"JWST stage configuration jwst.{stage_name} must be a mapping."
        )

    return dict(options)


def main(stage_name, input_file, output_dir, options):
    if not has_network_access():
        os.environ["CRDS_SERVER_URL"] = "https://jwst-serverless.stsci.edu"
        os.environ["STPIPE_DISABLE_CRDS_STEPPARS"] = "True"

    stage_module, stage_class = STAGE_IMPORTS[stage_name]
    module = importlib.import_module(stage_module)
    pipeline_class = getattr(module, stage_class)

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

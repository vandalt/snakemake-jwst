import importlib
import os
import socket
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

input_file = snakemake.input[0]
stage_name = snakemake.params["stage_name"]
pipeline_config = snakemake.config["jwst"][stage_name]
output_dir = Path(snakemake.output[0]).parent


def has_network_access(host="8.8.8.8", port=443, timeout=3):
    """
    Check for network access by attempting a quick socket connection.
    Kept here to avoid any imports before settings environment variables

    Coded with copilot.
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except (TimeoutError, OSError):
        return False


# NOTE: This must be run before importing the pipeline
if not has_network_access():
    os.environ["CRDS_SERVER_URL"] = "https://jwst-serverless.stsci.edu"
    os.environ["STPIPE_DISABLE_CRDS_STEPPARS"] = "True"


def main(stage_name, input_file, pipeline_config):
    # Importing inside function to avoid memory leak
    # Ref: https://jwst-pipeline.readthedocs.io/en/latest/jwst/user_documentation/running_pipeline_python.html#multiprocessing
    stage_module, stage_class = STAGE_IMPORTS[stage_name]
    module = importlib.import_module(stage_module)
    pipeline_class = getattr(module, stage_class)

    # Unless user explicitly does not want to save result, set it
    pipeline_config.setdefault("save_results", True)

    # TODO: Uncomment later
    # if stage_name == "kpi3":
    # pipeline_config = add_kpi_trim_cent(pipeline_config, input_file, position_file)
    # pipeline_config = add_kpi_trim_cent(pipeline_config, input_file, None)

    pipeline_class.call(input_file, output_dir=str(output_dir), **pipeline_config)


main(stage_name, input_file, pipeline_config)

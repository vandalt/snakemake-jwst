import runpy
import shutil
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY_ROOT = Path(__file__).parents[1]
WRAPPER = REPOSITORY_ROOT / "wrappers" / "jwst" / "wrapper.py"
TEST_SNAKEFILE = REPOSITORY_ROOT / "wrappers" / "jwst" / "test" / "Snakefile"


def test_wrapper_dry_run() -> None:
    result = subprocess.run(
        [
            shutil.which("snakemake"),
            "--snakefile",
            str(TEST_SNAKEFILE),
            "--dry-run",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "test_jwst_detector1" in result.stdout


def test_wrapper_rejects_unknown_stage() -> None:
    snakemake = SimpleNamespace(
        params={"stage_name": "unknown"},
        input=["input.fits"],
        output=["output.fits"],
        config={"jwst": {}},
        log=[],
    )

    with pytest.raises(ValueError, match="Expected one of: .*wfs-image3"):
        runpy.run_path(str(WRAPPER), init_globals={"snakemake": snakemake})


def test_wrapper_discovers_pipeline_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jwst.pipeline import Detector1Pipeline

    calls = []

    def call(input_file: str, output_dir: str, **options: object) -> None:
        calls.append((input_file, output_dir, options))

    options = {"save_calibrated_ramp": True}
    snakemake = SimpleNamespace(
        params={"stage_name": "detector1"},
        input=["input.fits"],
        output=["results/output.fits"],
        config={"jwst": {"detector1": options}},
        log=[],
    )

    def no_network(*args: object, **kwargs: object) -> None:
        raise OSError

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(Detector1Pipeline, "call", staticmethod(call))

    wrapper = runpy.run_path(str(WRAPPER), init_globals={"snakemake": snakemake})

    assert options == {"save_calibrated_ramp": True}
    assert calls == [
        (
            "input.fits",
            "results",
            {"save_calibrated_ramp": True, "save_results": True},
        )
    ]
    assert {
        "ami3",
        "coron3",
        "dark",
        "detector1",
        "guider",
        "image2",
        "image3",
        "kpi3",
        "spec2",
        "spec3",
        "tso3",
        "wfs-image3",
    }.issubset(wrapper["available_stages"]())


def test_wrapper_uses_pipeline_defaults_without_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jwst.pipeline import Image2Pipeline

    calls = []

    def call(input_file: str, output_dir: str, **options: object) -> None:
        calls.append((input_file, output_dir, options))

    snakemake = SimpleNamespace(
        params={"stage_name": "image2"},
        input=["input.fits"],
        output=["results/output.fits"],
        config={},
        log=[],
    )

    monkeypatch.setattr(Image2Pipeline, "call", staticmethod(call))

    runpy.run_path(str(WRAPPER), init_globals={"snakemake": snakemake})

    assert calls == [("input.fits", "results", {"save_results": True})]

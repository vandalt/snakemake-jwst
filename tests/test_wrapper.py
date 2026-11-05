import importlib
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

    with pytest.raises(ValueError, match="Unsupported JWST stage"):
        runpy.run_path(str(WRAPPER), init_globals={"snakemake": snakemake})


def test_wrapper_does_not_mutate_shared_stage_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class FakePipeline:
        @staticmethod
        def call(input_file: str, output_dir: str, **options: object) -> None:
            calls.append((input_file, output_dir, options))

    options = {}
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
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda module_name: SimpleNamespace(Detector1Pipeline=FakePipeline),
    )

    runpy.run_path(str(WRAPPER), init_globals={"snakemake": snakemake})

    assert options == {}
    assert calls == [("input.fits", "results", {"save_results": True})]

import os
import runpy
import shutil
import socket
import subprocess
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

REPOSITORY_ROOT = Path(__file__).parents[1]
WRAPPER = REPOSITORY_ROOT / "wrappers" / "jwst" / "wrapper.py"
TEST_SNAKEFILE = REPOSITORY_ROOT / "wrappers" / "jwst" / "test" / "Snakefile"
REAL_DATA_SNAKEFILE = (
    REPOSITORY_ROOT / "wrappers" / "jwst" / "test" / "real_data.Snakefile"
)
REAL_DATA_URL = (
    "https://mast.stsci.edu/api/v0.1/Download/file?"
    "uri=mast:JWST/product/jw01230009001_03103_00001_nis_uncal.fits"
)
REAL_DATA_FILE = (
    REPOSITORY_ROOT / "tests" / "data" / "jw01230009001_03103_00001_nis_uncal.fits"
)


def has_valid_real_data_file(input_file: Path) -> bool:
    from astropy.io import fits
    from astropy.io.fits.verify import VerifyError

    try:
        with fits.open(input_file, memmap=True) as hdul:
            hdul.verify("exception")
            return (
                hdul[0].header.get("INSTRUME") == "NIRISS"
                and hdul[0].header.get("DETECTOR") == "NIS"
                and hdul[0].header.get("EXP_TYPE") == "NIS_IMAGE"
                and {"SCI", "GROUP", "INT_TIMES", "ASDF"}.issubset(
                    hdu.name for hdu in hdul
                )
            )
    except (OSError, VerifyError):
        return False


def download_real_data_if_needed(input_file: Path) -> None:
    if has_valid_real_data_file(input_file):
        return

    input_file.parent.mkdir(parents=True, exist_ok=True)
    downloaded_file = input_file.with_suffix(".fits.download")
    downloaded_file.unlink(missing_ok=True)
    download = subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "3",
            "--output",
            str(downloaded_file),
            REAL_DATA_URL,
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert download.returncode == 0, download.stderr
    assert has_valid_real_data_file(downloaded_file)
    downloaded_file.replace(input_file)


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


@pytest.mark.integration
def test_wrapper_runs_detector1_on_real_data(tmp_path: Path) -> None:
    input_file = REAL_DATA_FILE
    output_file = tmp_path / "output" / "jw01230009001_03103_00001_nis_rate.fits"
    log_file = tmp_path / "logs" / "detector1.log"

    download_real_data_if_needed(input_file)

    environment = os.environ | {
        "CRDS_PATH": str(tmp_path / "crds"),
        "CRDS_SERVER_URL": "https://jwst-crds.stsci.edu",
    }
    result = subprocess.run(
        [
            shutil.which("snakemake"),
            "--snakefile",
            str(REAL_DATA_SNAKEFILE),
            "--use-conda",
            "--conda-prefix",
            str(tmp_path / "conda"),
            "--cores",
            "1",
            "--config",
            f"input_file={input_file}",
            f"output_file={output_file}",
            f"log_file={log_file}",
        ],
        capture_output=True,
        check=False,
        cwd=tmp_path,
        env=environment,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output_file.exists()

    from astropy.io import fits

    with fits.open(output_file) as rate:
        assert rate[0].header["INSTRUME"] == "NIRISS"
        assert rate[0].header["DETECTOR"] == "NIS"
        assert rate[0].header["EXP_TYPE"] == "NIS_IMAGE"
        assert rate[0].header["FILENAME"] == output_file.name
        assert "SCI" in rate
        assert "GROUP" not in rate


def test_real_data_download_is_skipped_when_cached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from astropy.io import fits

    input_file = tmp_path / REAL_DATA_FILE.name
    fits.HDUList(
        [
            fits.PrimaryHDU(
                header=fits.Header(
                    {"INSTRUME": "NIRISS", "DETECTOR": "NIS", "EXP_TYPE": "NIS_IMAGE"}
                )
            ),
            fits.ImageHDU(name="SCI"),
            fits.ImageHDU(name="GROUP"),
            fits.ImageHDU(name="INT_TIMES"),
            fits.ImageHDU(name="ASDF"),
        ]
    ).writeto(input_file)

    def unexpected_download(*args: object, **kwargs: object) -> None:
        pytest.fail("curl should not run when valid test data is cached")

    monkeypatch.setattr(subprocess, "run", unexpected_download)

    download_real_data_if_needed(input_file)


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
    monkeypatch.setenv("CRDS_SERVER_URL", "https://example.test/crds")
    monkeypatch.setenv("STPIPE_DISABLE_CRDS_STEPPARS", "False")

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
    assert os.environ["CRDS_SERVER_URL"] == "https://jwst-serverless.stsci.edu"
    assert os.environ["STPIPE_DISABLE_CRDS_STEPPARS"] == "True"
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


def test_wrapper_preserves_crds_environment_when_online(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from jwst.pipeline import Image2Pipeline

    calls = []
    connection_attempts = []
    monkeypatch.setenv("CRDS_SERVER_URL", "https://example.test/crds")
    monkeypatch.setenv("STPIPE_DISABLE_CRDS_STEPPARS", "False")

    def online_connection(*args: object, **kwargs: object) -> object:
        connection_attempts.append((args, kwargs))
        return nullcontext()

    def call(input_file: str, output_dir: str, **options: object) -> None:
        calls.append((input_file, output_dir, options))

    snakemake = SimpleNamespace(
        params={"stage_name": "image2"},
        input=["input.fits"],
        output=["results/output.fits"],
        config={},
        log=[],
    )

    monkeypatch.setattr(socket, "create_connection", online_connection)
    monkeypatch.setattr(Image2Pipeline, "call", staticmethod(call))

    runpy.run_path(str(WRAPPER), init_globals={"snakemake": snakemake})

    assert connection_attempts == [((("8.8.8.8", 443),), {"timeout": 3})]
    assert os.environ["CRDS_SERVER_URL"] == "https://example.test/crds"
    assert os.environ["STPIPE_DISABLE_CRDS_STEPPARS"] == "False"
    assert calls == [("input.fits", "results", {"save_results": True})]


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

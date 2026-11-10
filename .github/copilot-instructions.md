# Copilot Instructions

## Commands

This project uses `uv` and supports Python 3.11 through 3.14.

```bash
# Run all tests
uv run pytest

# Run one test
uv run pytest tests/test_wrapper.py::test_wrapper_dry_run

# Lint
uv run ruff check .

# Validate the bundled wrapper workflow without running JWST
uv run snakemake --snakefile wrappers/jwst/test/Snakefile --dry-run
```

The bundled workflow runs the wrapper through its local `file:wrappers/jwst`
reference. Running a real wrapper workflow requires Snakemake's `--use-conda`
so that `wrappers/jwst/environment.yaml` supplies the pinned JWST runtime.

## Architecture

The repository publishes one reusable Snakemake wrapper under
`wrappers/jwst`. Consuming workflows declare their own inputs, outputs, logs,
resources, and dependencies, then select this wrapper with `wrapper:`.
`meta.yaml` is the user-facing wrapper interface and `environment.yaml`
defines the isolated runtime.

`wrapper.py` is the adapter between Snakemake and JWST pipelines. It:

1. Reads `params.stage_name`, the first declared input, and the parent
   directory of the first declared output.
2. Discovers upstream JWST pipeline classes dynamically from their
   `calwebb_*` aliases, then adds the WFS combine step and the `jwst-kpi`
   `kpi3` pipeline.
3. Passes per-stage configuration to the selected pipeline and invokes its
   `.call()` method.

`tests/test_wrapper.py` executes the wrapper via `runpy` with a minimal mocked
`snakemake` object. The dry-run test covers the example workflow, while the
other tests cover pipeline selection, option forwarding, and defaults without
executing calibration work.

## Wrapper conventions

Follow the [Snakemake wrappers contribution guidance](https://snakemake-wrappers.readthedocs.io/en/stable/contributing.html)
when changing wrapper metadata, environments, tests, or publication readiness.

- The required stage name is the upstream `class_alias` with `calwebb_`
  removed (for example, `calwebb_detector1` becomes `detector1`). Keep stage
  discovery dynamic rather than maintaining a static stage list.
- Optional JWST options are read only from
  `config["jwst"][params.stage_name]`. Both `jwst` and each stage's options
  must be mappings; copy options before adding defaults so the Snakemake
  configuration is not mutated.
- The wrapper supplies `save_results=True` unless the selected stage config
  explicitly overrides it.
- If network access is unavailable, set the CRDS serverless endpoint and
  disable CRDS step-parameter retrieval before loading the pipeline.
- A `log:` directive is optional. When present, redirect both Python stdout
  and stderr to its first path, creating its parent directory first.
- The wrapper intentionally consumes only the first input/output path:
  output placement is controlled by the parent directory of the first output.

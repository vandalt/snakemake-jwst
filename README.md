# Snakemake wrapper for the JWST pipeline

This repository provides a reusable [Snakemake wrapper](https://snakemake-wrappers.readthedocs.io/) for the [JWST calibration pipeline](https://jwst-pipeline.readthedocs.io/).

## Use the wrapper

Define your workflow's rules, products, resource requests, and dependencies in the consuming project.

Use the wrapper in your project's `Snakefile` via the `wrapper:` directive.
Each rule must specify a pipeline stage via the `stage_name` parameter.
Here is an example with the `calwebb_detector1` pipeline:

```python
configfile: "config.yaml"

rule detector1:
    input:
        "data/raw/{file_id}_uncal.fits"
    output:
        "data/detector1/{file_id}_rate.fits"
    log:
        "logs/detector1/{file_id}.log"
    params:
        stage_name="detector1"
    wrapper:
        "https://github.com/vandalt/snakemake-jwst/raw/<tag>/wrappers/jwst"
```

Replace `<tag>` with a release tag or commit SHA.
The wrapper's Conda environment is created automatically when executing with `--use-conda`.

## Configuration

Pipeline options are optional and can be configured globally under the selected stage directly in your Snakemake configuration file:

```yaml
jwst:
  detector1:
    save_calibrated_ramp: True
```

The wrapper passes `config["jwst"][params.stage_name]` to the corresponding pipeline class when present; omit `jwst` or a stage entry to use the pipeline defaults.
It defaults to `save_results: true` when omitted.

When network access is unavailable, the wrapper configures CRDS to use the serverless endpoint.

## Supported stages

It supports all available [JWST pipeline stages](https://jwst-pipeline.readthedocs.io/en/stable/jwst/pipeline/main.html#pipelines) and the 

All stages from the upstream JWST pipeline are supported.
Stage names are derived from the [stage alias](https://jwst-pipeline.readthedocs.io/en/latest/jwst/pipeline/main.html) by removing the `calwebb_` prefix.
For example, `calwebb_detector` becomes `detector1` and `calwebb_image2` becomes `image2`.

The [jwst-kpi stage 3 pipeline](https://github.com/kammerje/jwst-kpi) is also supported.

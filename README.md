# Snakemake wrapper for the JWST pipeline

This repository provides a reusable
[Snakemake wrapper](https://snakemake-wrappers.readthedocs.io/) for the
[JWST calibration pipeline](https://jwst-pipeline.readthedocs.io/). It
supports the `detector1`, `image2`, `image3`, and `kpi3` pipeline stages.

## Use the wrapper

Define your workflow's rules, products, resource requests, and dependencies in
the consuming project. Each rule selects a stage with `params.stage_name`:

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

Replace `<tag>` with a release tag or commit SHA. The wrapper's Conda
environment is created automatically when executing with `--use-conda`.

## Configuration

Pipeline options are configured globally under the selected stage:

```yaml
jwst:
  detector1:
    save_results: true
  image2: {}
  image3: {}
  kpi3: {}
```

The wrapper passes `config["jwst"][params.stage_name]` to the corresponding
pipeline class. It defaults `save_results` to `true` when omitted. Declare
the expected output products in each consumer rule; the parent directory of
the first output is supplied to the pipeline as its output directory.

When network access is unavailable, the wrapper configures CRDS to use the
serverless endpoint.

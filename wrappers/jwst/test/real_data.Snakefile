from pathlib import Path


rule test_jwst_detector1_real_data:
    input:
        config["input_file"],
    output:
        config["output_file"],
    log:
        config["log_file"],
    params:
        stage_name="detector1",
    wrapper:
        f"file:{Path(workflow.basedir).parent}"

# ExplainBench usage guide

This guide explains how to use the `explainbench` command.
It covers submission checks, evaluation, and local-effect question building.

## Contents

- [Before you start](#before-you-start)
- [Create a submission](#create-a-submission)
- [Check a submission](#check-a-submission)
- [Set model credentials](#set-model-credentials)
- [Run an evaluation](#run-an-evaluation)
- [Use an evaluation configuration file](#use-an-evaluation-configuration-file)
- [Continue an interrupted evaluation](#continue-an-interrupted-evaluation)
- [Read the result file](#read-the-result-file)
- [Build local-effect question files](#build-local-effect-question-files)
- [Manage question builder files](#manage-question-builder-files)
- [Get help](#get-help)

## Before you start

Install Python 3.12 and ExplainBench:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install explainbench-cli
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Check the command:

```bash
explainbench --version
explainbench --help
```

## Create a submission

A submission is a UTF-8 JSON file.
It contains one submission ID and one or more instances.

Use this form:

```json
{
  "submission_id": "my-run",
  "instances": [
    {
      "instance_id": "sympy__sympy-15349",
      "explanation": "The patch fixes the sign used in the rotation matrix.",
      "model_patch": "diff --git a/sympy/algebras/quaternion.py b/sympy/algebras/quaternion.py\n--- a/sympy/algebras/quaternion.py\n+++ b/sympy/algebras/quaternion.py\n@@ -529,7 +529,7 @@ def to_rotation_matrix(self, v=None):\n \n         m10 = 2*s*(q.b*q.c + q.d*q.a)\n         m11 = 1 - 2*s*(q.b**2 + q.d**2)\n-        m12 = 2*s*(q.c*q.d + q.b*q.a)\n+        m12 = 2*s*(q.c*q.d - q.b*q.a)\n \n         m20 = 2*s*(q.b*q.d - q.c*q.a)\n         m21 = 2*s*(q.c*q.d + q.b*q.a)\n"
    }
  ]
}
```

The fields have these meanings:

| Field | Required | Meaning |
| --- | --- | --- |
| `submission_id` | Yes | A name for this submission. |
| `instances` | Yes | A list with at least one benchmark instance. |
| `instance_id` | Yes | An instance ID that ExplainBench supports. |
| `explanation` | Yes | The explanation that you want to evaluate. |
| `model_patch` | For effect tasks | The code change as a Git unified diff. |

Each `instance_id` must be unique in one submission.
The text fields must not be empty.
ExplainBench rejects unknown fields.

The `model_patch` field is optional when you only use intent tasks.
It is required for `e2e.effect`, `local.effect`, full mode, and the local-effect question builder.

For effect tasks, use only letters, numbers, periods, underscores, and hyphens in `submission_id`.

The installed source repository includes sample files in its `examples` directory.

## Check a submission

Run the checker before an evaluation:

```bash
explainbench checker submission.json
```

A valid file produces output like this:

```text
Submission is valid
Submission ID: my-run
Instances: 1
Explanations: 1
Patches: 1
```

An invalid file produces a list of problems and returns exit code 1.

The checker checks the basic file format.
An effect evaluation and the question builder also check that each instance has a patch.

## Set model credentials

Evaluation sends data to the model provider that serves the selected model.
The local-effect question builder can also send data to a model provider.
These requests can cause a charge.

Set the environment variable that your provider needs.
For OpenAI, use:

```bash
export OPENAI_API_KEY="your-api-key"
```

You can also put credentials in a `.env` file:

```dotenv
OPENAI_API_KEY=your-api-key
```

Pass that file to an evaluation:

```bash
explainbench evaluate submission.json \
  --mode lite \
  --model MODEL_ID \
  --env-file .env \
  --output results.json
```

Use `--candidate-env-file .env` when the local-effect question builder needs the file.

Do not commit a credential file to Git.

## Run an evaluation

An evaluation asks a model questions about each explanation.
ExplainBench scores the answers and writes one JSON result file.

You can select a mode or select tasks directly.
Do not use `--mode` and `--task` in the same command.

### Lite mode

Lite mode runs these tasks:

- `e2e.intent`
- `local.intent`

The needed intent question data is included in the package.
The submission does not need `model_patch` values.

Run lite mode:

```bash
explainbench evaluate submission.json \
  --mode lite \
  --model MODEL_ID \
  --num-generations 1 \
  --output results.json
```

### Full mode

Full mode runs these tasks:

- `e2e.intent`
- `e2e.effect`
- `local.intent`
- `local.effect`

Full mode needs a patch for each instance.
It also needs effect question files that match the `submission_id`.

Run full mode:

```bash
explainbench evaluate submission.json \
  --mode full \
  --model MODEL_ID \
  --artifacts-dir question-artifacts \
  --output results.json
```

The effect question directory must have this form:

```text
question-artifacts/
├── context/
│   ├── e2e_effect__my-run.json
│   └── local_effect__my-run.json
└── ground_truths/
    ├── e2e_effect__my-run.json
    └── local_effect__my-run.json
```

The local-effect question builder creates the `local_effect` pair.
You must provide the `e2e_effect` pair before you run all four full-mode tasks.

### Select tasks directly

Use `--task` when you do not want a full mode.
Repeat the option to select more than one task:

```bash
explainbench evaluate submission.json \
  --task e2e.intent \
  --task local.intent \
  --model MODEL_ID \
  --output results.json
```

These tasks are available:

| Task | What it checks | Extra question files |
| --- | --- | --- |
| `e2e.intent` | Whether the explanation states the full change goal. | No |
| `e2e.effect` | Whether the explanation states the effect of the patch on a test. | Yes |
| `local.intent` | Whether the explanation states the intended change at a code location. | No |
| `local.effect` | Whether the explanation states how values change at a code location. | Yes |

### Set the number of model answers

`--num-generations` sets the number of model answers for each task instance.
A larger value uses more model requests.
The default value is 5.

This example asks for one answer:

```bash
explainbench evaluate submission.json \
  --mode lite \
  --model MODEL_ID \
  --num-generations 1 \
  --output results.json
```

### Set parallel work

Use `--workers` to set the number of instances that can run at the same time.
Use `--generation-workers` to set the number of answers for one instance that can run at the same time.

Start with low values if your provider has strict request limits:

```bash
explainbench evaluate submission.json \
  --mode lite \
  --model MODEL_ID \
  --workers 2 \
  --generation-workers 1 \
  --output results.json
```

### Other evaluation options

Use these options when you need more control:

| Option | Purpose |
| --- | --- |
| `--temperature NUMBER` | Set the model sampling temperature. |
| `--top-p NUMBER` | Set the model top-p value. |
| `--max-tokens NUMBER` | Set the response token limit. |
| `--max-retries NUMBER` | Set the maximum attempts for one model request. |
| `--no-progress` | Hide progress bars. |
| `--env-file PATH` | Load model credentials from a file. |
| `--artifacts-dir PATH` | Select the effect question directory. |
| `--output PATH` | Select the result JSON file. |

Command-line options replace values from a configuration file.

## Use an evaluation configuration file

A TOML file can store the evaluation settings.
Paths in the file are relative to the directory that contains the file.

Create `evaluation.toml`:

```toml
schema_version = 1

[selection]
mode = "lite"

[evaluator]
model = "MODEL_ID"
num_generations = 1
instance_workers = 2
generation_workers = 1
temperature = 1.0
top_p = 1.0
max_tokens = 8192
max_retries = 5

[paths]
output = "results.json"

[environment]
env_file = ".env"
```

Run the evaluation:

```bash
explainbench evaluate submission.json --config evaluation.toml
```

To select tasks instead of a mode, replace the selection block:

```toml
[selection]
tasks = ["e2e.intent", "local.intent"]
```

For a full evaluation, add `artifacts_dir`:

```toml
[paths]
artifacts_dir = "question-artifacts"
output = "results.json"
```

## Continue an interrupted evaluation

ExplainBench writes a checkpoint next to the result path while an evaluation runs.
For `results.json`, the checkpoint is `results.json.checkpoint.jsonl`.

Run the same command with `--resume`:

```bash
explainbench evaluate submission.json \
  --mode lite \
  --model MODEL_ID \
  --output results.json \
  --resume
```

ExplainBench reuses completed work only when the submission and main evaluation settings match.
It keeps the checkpoint when any task instance fails.
It removes the checkpoint after all selected work succeeds.

## Read the result file

The result is a JSON file with:

- The submission ID.
- The selected mode and tasks.
- The model settings.
- Token use reported by the model provider.
- The mean score and standard error for each task.
- Counts for completed, skipped, and failed instances.
- Predictions and scores for each completed instance.
- Error text for each failed instance.

The command prints the result path when it finishes.

## Build local-effect question files

The local-effect builder makes question data for the `local.effect` task.
It uses the submitted patch and runs code before and after that patch.

### Builder requirements

Before you start, provide:

- Python 3.12 with ExplainBench installed.
- A running Docker service.
- At least 20 GB of free disk space for a first run.
- Network access to Python package indexes.
- Network access to the Git host for each benchmark repository.
- Network access to Hugging Face for the SWE-bench data.
- Network access to the Docker image services used by SWE-bench.
- A model key for candidate generation.

The first run can take a long time because it can download and build Docker images.

### Run all stages

Use a separate workspace for each submission:

```bash
explainbench question-builder local run submission.json \
  --workspace .explainbench/builds/my-run \
  --output question-artifacts \
  --candidate-model MODEL_ID \
  --resume
```

The workspace stores source repositories, Docker run data, logs, model responses, and checkpoints.
The output directory contains the finished question files.

The command can make paid model requests during candidate generation.

### Check progress

Run:

```bash
explainbench question-builder local status \
  --workspace .explainbench/builds/my-run
```

The command shows the state of each stage and any failure.

### Continue a stopped build

Run the same build command with `--resume`.
The builder reuses completed work when the submission and settings match.

Do not run two builders in the same workspace at the same time.

### List the stages

Run:

```bash
explainbench question-builder local stages
```

The builder has these stages:

1. Find the changed Python functions.
2. Find tests that call those functions.
3. Select functions for detailed tracing.
4. Record program values before and after the patch.
5. Find the first useful difference.
6. Generate candidate expressions.
7. Run the candidate expressions.
8. Check which expressions changed.
9. Build the answer choices.
10. Write the final question files.

### Run one stage

You can run one stage by name:

```bash
explainbench question-builder local stage identify-patched-functions \
  submission.json \
  --workspace .explainbench/builds/my-run
```

A stage needs the output from all earlier stages.
Use the full `run` command unless you need to inspect or repeat one stage.

### Use a builder configuration file

Create `builder.toml`:

```toml
schema_version = 1

[execution]
workers = 1
max_attempts = 3
candidate_generation_changed_candidates = 10
candidate_generation_unchanged_candidates = 10
candidate_generation_inference = true

[models]
candidate_generation = "MODEL_ID"

[paths]
workspace = ".explainbench/builds/my-run"
output = "question-artifacts"
candidate_generation_env_file = ".env"

[benchmark]
dataset_name = "SWE-bench/SWE-bench_Verified"
repository_remote = "https://github.com"
```

Run:

```bash
explainbench question-builder local run submission.json \
  --config builder.toml \
  --resume
```

Command-line options replace values from the file.
Run `explainbench question-builder local run --help` to see all builder settings.

## Manage question builder files

Keep the workspace while you need to continue or inspect a build.
The workspace can contain source code, test output, prompts, and model responses.
Treat it as private data.

The output path is a link to a fixed result directory inside the workspace.
Copy the output to another safe directory before you delete the workspace.

Delete a workspace only when:

- No builder process uses it.
- You do not need its logs.
- You do not need to continue the build.

## Get help

Show help for any command:

```bash
explainbench --help
explainbench checker --help
explainbench evaluate --help
explainbench question-builder local --help
explainbench question-builder local run --help
```

If a command fails, read the first error message and check the named file or setting.
For more help, open an issue in the [GitHub issue tracker](https://github.com/explainbench/explainbench-cli/issues).

# ExplainBench CLI

ExplainBench checks and evaluates explanations of code changes.
It can also build the question files that are needed for a full evaluation.

The project website is [explainbench.github.io](https://explainbench.github.io).

## What you can do

- Check the format of an ExplainBench submission.
- Run a lite evaluation of patch explanations.
- Run a full evaluation with effect question files.
- Build local-effect question files for a submission.
- Continue an evaluation or question build after an interruption.

## Requirements

ExplainBench requires Python 3.12.

The submission checker has no extra service requirements.
An evaluation needs network access and a key for the selected model provider.
The local-effect question builder also needs Docker and access to the required code and data services.

## Installation

Create and activate a Python 3.12 virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.venv\Scripts\Activate.ps1
```

Install ExplainBench:

```bash
python -m pip install --upgrade pip
python -m pip install explainbench-cli
```

Check the installation:

```bash
explainbench --version
explainbench --help
```

## Quick start

### 1. Create a submission file

Save this example as `submission.json`:

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

The `model_patch` field is optional for a lite evaluation.
It is required for a full evaluation and for the local-effect question builder.

### 2. Check the submission

```bash
explainbench checker submission.json
```

The command prints `Submission is valid` when the file is ready.
If the file is not valid, the command lists each problem.

### 3. Run a lite evaluation

Set the key for your model provider.
For an OpenAI model, use:

```bash
export OPENAI_API_KEY="your-api-key"
```

Then run:

```bash
explainbench evaluate submission.json \
  --mode lite \
  --model MODEL_ID \
  --num-generations 1 \
  --output results.json
```

Replace `MODEL_ID` with the model that you want to use.
This command sends the explanations to the model provider and can cause a charge.

## Full evaluation

A full evaluation needs both end-to-end effect files and local-effect files.
The local question builder creates the local-effect files:

```bash
explainbench question-builder local run submission.json \
  --workspace .explainbench/builds/my-run \
  --output question-artifacts \
  --resume
```

Add the matching end-to-end effect files to the same output directory.
See the [detailed usage guide](https://github.com/explainbench/explainbench-cli/blob/main/USAGE.md#full-mode) for the required file names.

Then run:

```bash
explainbench evaluate submission.json \
  --mode full \
  --model MODEL_ID \
  --artifacts-dir question-artifacts \
  --output results.json \
  --resume
```

The question builder uses Docker, downloads data and source code, and can call a model.
Read the setup steps before you run it.

## Detailed guide

See the [ExplainBench usage guide](https://github.com/explainbench/explainbench-cli/blob/main/USAGE.md) for:

- The full submission file format.
- Lite and full evaluation modes.
- Direct task selection.
- Configuration files.
- Resume and output behavior.
- Local-effect question builder setup.
- Common errors and fixes.

You can also add `--help` after any command:

```bash
explainbench evaluate --help
explainbench question-builder local run --help
```

## Get help

Report a problem in the [GitHub issue tracker](https://github.com/explainbench/explainbench-cli/issues).

## License

ExplainBench is available under the [MIT License](LICENSE).
The distribution includes the SWE-bench notice in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

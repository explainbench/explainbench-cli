"""Smoke-test an installed release artifact outside the source repository."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib.metadata import distribution, metadata
from pathlib import Path

import dataset
import execution
import explainbench
import tracer

from explainbench import cli
from explainbench.evaluation import service


INSTANCE_ID = "astropy__astropy-12907"


class FakeEvaluator:
    """Return deterministic structured answers without a model request."""

    def __init__(self, model_id, **sampling_params):
        self.num_generations = sampling_params["n"]
        self.token_usage = {
            "completion_tokens": 2,
            "prompt_tokens": 10,
            "total_tokens": 12,
        }

    def infer(self, messages, schema):
        if "before_selection" in schema.model_fields:
            payload = {"before_selection": "a", "after_selection": "a"}
        else:
            payload = {"answer": ["d"]}
        return [
            schema.model_validate(payload)
            for _ in range(self.num_generations)
        ]


def _assert_installed_metadata() -> None:
    for package in (dataset, execution, explainbench, tracer):
        location = Path(package.__file__).resolve()
        assert "site-packages" in location.parts, location

    package_metadata = metadata("explainbench-cli")
    requires_python = package_metadata["Requires-Python"]
    assert ">=3.12" in requires_python
    assert "<3.13" in requires_python
    assert package_metadata["License-Expression"] == "MIT"

    files = {
        str(path)
        for path in (distribution("explainbench-cli").files or ())
    }
    assert any(path.endswith(".dist-info/licenses/LICENSE") for path in files)
    assert any(
        path.endswith(".dist-info/licenses/THIRD_PARTY_NOTICES.md")
        for path in files
    )
    assert not any(".explainbench/" in path for path in files)
    assert not any(path.startswith("tests/") for path in files)


def _run_installed_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    executable = Path(sys.executable).with_name("explainbench")
    assert executable.is_file(), executable
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    return subprocess.run(
        [str(executable), *arguments],
        cwd=Path.cwd(),
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_submission(root: Path) -> Path:
    submission = root / "submission.json"
    submission.write_text(
        json.dumps(
            {
                "submission_id": "release-artifact-smoke",
                "instances": [
                    {
                        "instance_id": INSTANCE_ID,
                        "explanation": (
                            "The relevant answer is described by option d."
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return submission


def _check_cli_and_builder(submission: Path) -> None:
    help_result = _run_installed_cli("--help")
    assert help_result.returncode == 0, help_result.stderr
    assert "evaluate" in help_result.stdout
    assert "question-builder" in help_result.stdout

    checker_result = _run_installed_cli("checker", str(submission))
    assert checker_result.returncode == 0, checker_result.stderr
    assert "Submission is valid" in checker_result.stdout

    stages_result = _run_installed_cli(
        "question-builder",
        "local",
        "stages",
    )
    assert stages_result.returncode == 0, stages_result.stderr
    stage_lines = stages_result.stdout.splitlines()
    assert len(stage_lines) == 10
    assert "identify-patched-functions" in stage_lines[0]
    assert "export-question-artifacts" in stage_lines[-1]


def _check_mocked_evaluator(submission: Path, root: Path) -> None:
    result_path = root / "evaluation.json"
    service.Model = FakeEvaluator
    status = cli.main(
        [
            "evaluate",
            str(submission),
            "--mode",
            "lite",
            "--model",
            "release-artifact-fake",
            "--num-generations",
            "1",
            "--workers",
            "1",
            "--no-progress",
            "--output",
            str(result_path),
        ]
    )
    assert status == 0
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["selection"] == {
        "mode": "lite",
        "tasks": ["e2e.intent", "local.intent"],
    }
    assert all(
        task["counts"]["evaluated"] == 1
        for task in result["tasks"].values()
    )
    assert all(not task["failures"] for task in result["tasks"].values())


def main() -> None:
    root = Path.cwd()
    _assert_installed_metadata()
    submission = _write_submission(root)
    _check_cli_and_builder(submission)
    _check_mocked_evaluator(submission, root)
    print("installed release artifact smoke passed")


if __name__ == "__main__":
    main()

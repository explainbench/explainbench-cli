"""Run and resume the first canonical builder stage from the installed wheel."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import CleanWheel


INSTANCE_ID = "sympy__sympy-15349"
PATCH = """\
diff --git a/module.py b/module.py
--- a/module.py
+++ b/module.py
@@ -1,2 +1,2 @@
 def changed():
-    return 1
+    return 2
"""
MOCKED_PIPELINE = """\
import importlib.util
import json
import sys
from pathlib import Path

from dataset.extract_ground_truths.effect.paid_inference import (
    PaidInferenceJournal,
)
from explainbench import cli
from explainbench.evaluation.artifacts import load_task_artifacts
from explainbench.question_builders.local import runners
from explainbench.question_builders.local.registry import LOCAL_STAGE_REGISTRY
from explainbench.question_builders.local.workspace import LocalBuilderWorkspace


def argument_value(arguments, option):
    return arguments[arguments.index(option) + 1]


def write_harness_output(arguments, context, payload, *, inspection=False):
    work_option = "--inspection-work-dir" if inspection else "--work-dir"
    run_option = (
        "--inspection-run-id-template"
        if inspection
        else "--run-id"
    )
    root = (
        Path(argument_value(arguments, work_option))
        / "logs"
        / "run_evaluation"
        / argument_value(arguments, run_option)
        / context.submission_id
        / context.instance.instance_id
    )
    for name in ("buggy_traces", "patched_traces"):
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "test.jsonl").write_text(
            f"{json.dumps(payload)}\\n",
            encoding="utf-8",
        )


calls = []

canonical_modules = (
    runners.IDENTIFY_PATCHED_FUNCTIONS_MODULE,
    runners.TRACK_TEST_CALLS_MODULE,
    runners.SELECT_TRACE_FUNCTIONS_MODULE,
    runners.TRACE_PROGRAM_STATE_MODULE,
    runners.BUILD_STEP1_MODULE,
    runners.BUILD_STEP2_MODULE,
    runners.BUILD_STEP3_MODULE,
    runners.BUILD_STEP3_MODULE,
    runners.BUILD_STEP4_MODULE,
    runners.BUILD_STEP5_MODULE,
)
assert len(canonical_modules) == len(LOCAL_STAGE_REGISTRY.names)
for module in canonical_modules:
    specification = importlib.util.find_spec(module)
    assert specification is not None, module
    assert specification.origin is not None, module
    assert "site-packages" in Path(specification.origin).resolve().parts, (
        module,
        specification.origin,
    )


def fake_command(module, raw_arguments, context, **kwargs):
    arguments = tuple(raw_arguments)
    calls.append(module)
    instance_id = context.instance.instance_id
    submission_id = context.submission_id

    if module == runners.IDENTIFY_PATCHED_FUNCTIONS_MODULE:
        Path(argument_value(arguments, "--output-path")).write_text(
            json.dumps(
                {submission_id: {instance_id: ["module:changed"]}}
            ),
            encoding="utf-8",
        )
        return

    if module == runners.TRACK_TEST_CALLS_MODULE:
        write_harness_output(
            arguments,
            context,
            {"target": "module:changed", "stack": []},
        )
        return

    if module == runners.SELECT_TRACE_FUNCTIONS_MODULE:
        Path(argument_value(arguments, "--output-path")).write_text(
            json.dumps(
                {submission_id: {instance_id: ["module:changed"]}}
            ),
            encoding="utf-8",
        )
        return

    if module == runners.TRACE_PROGRAM_STATE_MODULE:
        write_harness_output(
            arguments,
            context,
            {"event": "line", "function": "module:changed"},
        )
        return

    if module == runners.BUILD_STEP1_MODULE:
        Path(argument_value(arguments, "--output-path")).write_text(
            json.dumps(
                {
                    submission_id: {
                        instance_id: {
                            "file_path": "module.py",
                            "function_name": "module:changed",
                            "buggy_event_type": "Line",
                            "patched_event_type": "Line",
                            "buggy_statement": "return 1",
                            "patched_statement": "return 2",
                            "before_or_after": "before",
                            "buggy_lineno": 2,
                            "patched_lineno": 2,
                            "diff": {"values_changed": {}},
                            "buggy_variables": {},
                            "patched_variables": {},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return

    if module == runners.BUILD_STEP2_MODULE:
        journal = PaidInferenceJournal(
            argument_value(arguments, "--audit-dir"),
            prompt="clean wheel candidate prompt",
            model_id=argument_value(arguments, "--model"),
            reasoning_effort=argument_value(arguments, "--reasoning-effort"),
            response_schema=(
                "dataset.extract_ground_truths.effect."
                "infer_expression.ExpressionList"
            ),
        )
        response = journal.record_response(
            '{"expressions":[{"expr":"value"}]}'
        )
        journal.select_response(response)
        Path(argument_value(arguments, "--output-path")).write_text(
            json.dumps(
                {
                    submission_id: {
                        instance_id: {
                            "instance_id": instance_id,
                            "agent": submission_id,
                            "file_path": "module.py",
                            "function_name": "module:changed",
                            "buggy_lineno": 2,
                            "patched_lineno": 2,
                            "buggy_line_count": 2,
                            "patched_line_count": 2,
                            "test_id": 0,
                            "before_or_after": "before",
                            "prompt_length_chars": 28,
                            "function_code_before_patch": (
                                "def changed():\\n    return 1"
                            ),
                            "buggy_function_param": {"value": 1},
                            "location": "before return 1",
                            "changed_candidates": ["value"],
                            "unchanged_candidates": [
                                "other",
                                "third",
                                "fourth",
                            ],
                            "_source_response": journal.selected_response(),
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return

    if module == runners.BUILD_STEP3_MODULE:
        if "--validate" in arguments:
            step2 = json.loads(
                Path(
                    argument_value(arguments, "--step2-path")
                ).read_text(encoding="utf-8")
            )
            metadata = step2[submission_id][instance_id]
            Path(argument_value(arguments, "--output-path")).write_text(
                json.dumps(
                    {
                        submission_id: {
                            instance_id: {
                                **metadata,
                                "valid_changed_expressions": ["value"],
                                "valid_unchanged_expressions": [
                                    "other",
                                    "third",
                                    "fourth",
                                ],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            return
        write_harness_output(
            arguments,
            context,
            {
                "expr": ["value", "other", "third", "fourth"],
                "value": [1, 2, 3, 4],
            },
            inspection=True,
        )
        return

    if module == runners.BUILD_STEP4_MODULE:
        step3 = json.loads(
            Path(
                argument_value(arguments, "--step3-path")
            ).read_text(encoding="utf-8")
        )
        metadata = step3[submission_id][instance_id]
        excluded = {
            "valid_changed_expressions",
            "valid_unchanged_expressions",
            "prompt_length_chars",
            "changed_candidates",
            "unchanged_candidates",
        }
        Path(argument_value(arguments, "--output-path")).write_text(
            json.dumps(
                {
                    submission_id: {
                        instance_id: {
                            "choices": [
                                "value",
                                "other",
                                "third",
                                "fourth",
                                runners.NONE_OF_THE_ABOVE_CHOICE,
                                runners.CANNOT_INFER_CHOICE,
                            ],
                            "answer": ["a"],
                            **{
                                key: value
                                for key, value in metadata.items()
                                if key not in excluded
                            },
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return

    if module == runners.BUILD_STEP5_MODULE:
        step4 = json.loads(
            Path(
                argument_value(arguments, "--effect-step4-path")
            ).read_text(encoding="utf-8")
        )
        question = step4[submission_id][instance_id]
        filename = f"local_effect__{submission_id}.json"
        context_directory = Path(argument_value(arguments, "--context-dir"))
        truth_directory = Path(argument_value(arguments, "--ground-truth-dir"))
        context_directory.mkdir(parents=True, exist_ok=True)
        truth_directory.mkdir(parents=True, exist_ok=True)
        (context_directory / filename).write_text(
            json.dumps(
                {
                    instance_id: {
                        "function_code_before_patch": question[
                            "function_code_before_patch"
                        ],
                        "function_parameters_before_patch": "{'value': 1}\\n",
                        "line": question["location"],
                        "choices": question["choices"],
                        "before_or_after": question["before_or_after"],
                    }
                }
            ),
            encoding="utf-8",
        )
        (truth_directory / filename).write_text(
            json.dumps({instance_id: {"answer": question["answer"]}}),
            encoding="utf-8",
        )
        return

    raise AssertionError(f"unexpected canonical module: {module}")


runners.run_canonical_module = fake_command
arguments = [
    "question-builder",
    "local",
    "run",
    sys.argv[1],
    "--workspace",
    sys.argv[2],
    "--output",
    sys.argv[3],
    "--workers",
    "1",
    "--max-attempts",
    "1",
    "--candidate-model",
    "clean-wheel-fake",
    "--candidate-changed-candidates",
    "1",
    "--candidate-unchanged-candidates",
    "3",
]
status = cli.main(arguments)
assert status == 0
assert len(calls) == 10

workspace = LocalBuilderWorkspace.inspect(sys.argv[2])
for stage in LOCAL_STAGE_REGISTRY.names:
    result = workspace.read_result(stage, sys.argv[4])
    assert result.outcome == "completed"

first_call_count = len(calls)
status = cli.main([*arguments, "--resume"])
assert status == 0
assert len(calls) == first_call_count

artifacts = load_task_artifacts(
    "local.effect",
    submission_id="clean-wheel-pipeline",
    artifacts_dir=sys.argv[3],
)
assert artifacts.instance_ids == {sys.argv[4]}
assert artifacts.ground_truths[sys.argv[4]].answer == ["a"]
print("clean mocked pipeline passed")
"""


def _assert_success(result, label: str) -> None:
    assert result.returncode == 0, (
        f"{label} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_clean_local_builder(clean_wheel: CleanWheel):
    stage_result = clean_wheel.run(
        [
            str(clean_wheel.executable),
            "question-builder",
            "local",
            "stages",
        ]
    )
    _assert_success(stage_result, "stage listing")
    stage_lines = [
        line for line in stage_result.stdout.splitlines() if line.strip()
    ]
    assert len(stage_lines) == 10
    assert "identify-patched-functions" in stage_lines[0]

    root = clean_wheel.run_directory / "local-builder"
    repository_cache = root / "repositories"
    repository = repository_cache / INSTANCE_ID / "owner" / "repository"
    repository.mkdir(parents=True)

    for arguments in (
        ["git", "init"],
        ["git", "config", "user.email", "clean-wheel@example.invalid"],
        ["git", "config", "user.name", "Clean Wheel"],
    ):
        result = clean_wheel.run(arguments, cwd=repository)
        _assert_success(result, "Git repository setup")

    (repository / "module.py").write_text(
        "def changed():\n    return 1\n",
        encoding="utf-8",
    )
    _assert_success(
        clean_wheel.run(["git", "add", "module.py"], cwd=repository),
        "Git add",
    )
    _assert_success(
        clean_wheel.run(
            ["git", "commit", "-m", "Create test repository"],
            cwd=repository,
        ),
        "Git commit",
    )
    revision_result = clean_wheel.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
    )
    _assert_success(revision_result, "Git revision")
    revision = revision_result.stdout.strip()

    dataset = root / "dataset.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "instance_id": INSTANCE_ID,
                    "repo": "owner/repository",
                    "base_commit": revision,
                    "patch": PATCH,
                }
            ]
        ),
        encoding="utf-8",
    )
    submission = root / "submission.json"
    submission.write_text(
        json.dumps(
            {
                "submission_id": "clean-wheel-agent",
                "instances": [
                    {
                        "instance_id": INSTANCE_ID,
                        "explanation": "The return value changed.",
                        "model_patch": PATCH,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    workspace = root / "workspace"
    command = [
        str(clean_wheel.executable),
        "question-builder",
        "local",
        "stage",
        "identify-patched-functions",
        str(submission),
        "--workspace",
        str(workspace),
        "--repository-cache",
        str(repository_cache),
        "--dataset-name",
        str(dataset),
        "--repository-remote",
        "https://example.invalid",
        "--max-attempts",
        "1",
    ]

    initial = clean_wheel.run(command)
    _assert_success(initial, "initial identify stage")
    assert "completed=1" in initial.stdout

    resumed = clean_wheel.run([*command, "--resume"])
    _assert_success(resumed, "resumed identify stage")
    assert "reused=1" in resumed.stdout

    instance_root = (
        workspace
        / "stages"
        / "identify-patched-functions"
        / "instances"
        / INSTANCE_ID
    )
    status = json.loads(
        (instance_root / "status.json").read_text(encoding="utf-8")
    )
    result = json.loads(
        (instance_root / "result.json").read_text(encoding="utf-8")
    )
    command_records = list((instance_root / "work").rglob("command.json"))

    assert status["state"] == "completed"
    assert status["total_attempts"] == 1
    assert result["data"]["qualnames"] == ["module:changed"]
    assert len(command_records) == 1

    import_result = clean_wheel.run_python(
        """
import importlib.util
import dataset
import execution
import tracer

for package in (dataset, execution, tracer):
    assert "site-packages" in package.__file__
assert importlib.util.find_spec("evaluation") is None

from dataset.extract_ground_truths.effect.infer_expression import (
    Model as CandidateModel,
)
from explainbench.evaluation.inference import Model

assert CandidateModel is Model
print("clean local builder passed")
"""
    )
    _assert_success(import_result, "installed core imports")
    assert import_result.stdout.strip() == "clean local builder passed"


def test_clean_mocked_local_builder_pipeline(clean_wheel: CleanWheel):
    root = clean_wheel.run_directory / "mocked-local-builder"
    root.mkdir()
    submission = root / "submission.json"
    submission.write_text(
        json.dumps(
            {
                "submission_id": "clean-wheel-pipeline",
                "instances": [
                    {
                        "instance_id": INSTANCE_ID,
                        "explanation": "The return value changed.",
                        "model_patch": PATCH,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    workspace = root / "workspace"
    artifacts = root / "artifacts"

    result = clean_wheel.run_python(
        MOCKED_PIPELINE,
        str(submission),
        str(workspace),
        str(artifacts),
        INSTANCE_ID,
    )

    _assert_success(result, "mocked installed-wheel builder pipeline")
    assert result.stdout.rstrip().endswith("clean mocked pipeline passed")


def test_clean_paid_response_survives_process_interruption(
    clean_wheel: CleanWheel,
):
    root = clean_wheel.run_directory / "paid-response-interruption"
    interrupted_audit = root / "interrupted-audit"
    resumed_audit = root / "resumed-audit"
    root.mkdir()

    interrupted = clean_wheel.run_python(
        """\
import os
import sys

from dataset.extract_ground_truths.effect.paid_inference import (
    PaidInferenceJournal,
)

journal = PaidInferenceJournal(
    sys.argv[1],
    prompt="clean wheel interruption prompt",
    model_id="clean-wheel-fake",
    reasoning_effort="medium",
    response_schema=(
        "dataset.extract_ground_truths.effect."
        "infer_expression.ExpressionList"
    ),
)
journal.record_response('{"expressions":[{"expr":"value"}]}')
os._exit(75)
""",
        str(interrupted_audit),
    )
    assert interrupted.returncode == 75

    resumed = clean_wheel.run_python(
        """\
import json
import sys
from pathlib import Path

from dataset.extract_ground_truths.effect.infer_expression import (
    ExpressionList,
)
from dataset.extract_ground_truths.effect.paid_inference import (
    PaidInferenceJournal,
)

journal = PaidInferenceJournal(
    sys.argv[1],
    prompt="clean wheel interruption prompt",
    model_id="clean-wheel-fake",
    reasoning_effort="medium",
    response_schema=(
        "dataset.extract_ground_truths.effect."
        "infer_expression.ExpressionList"
    ),
    resume_directories=(Path(sys.argv[2]),),
)
prediction = journal.reuse_response(ExpressionList)
assert prediction is not None
assert [item.expr for item in prediction.expressions] == ["value"]
manifest = json.loads(journal.manifest_path.read_text(encoding="utf-8"))
assert len(manifest["responses"]) == 1
assert manifest["responses"][0]["reused_from"]["path"] == (
    "responses/response-0001.txt"
)
assert manifest["selected_response"]["path"] == (
    "responses/response-0001.txt"
)
print("clean interrupted paid response reused")
""",
        str(resumed_audit),
        str(interrupted_audit),
    )
    _assert_success(resumed, "interrupted paid-response recovery")
    assert resumed.stdout.strip() == "clean interrupted paid response reused"

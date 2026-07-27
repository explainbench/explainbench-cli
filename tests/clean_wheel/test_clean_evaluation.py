"""Exercise evaluation behavior using only the installed wheel."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import CleanWheel


INSTANCE_ID = "astropy__astropy-12907"
VALID_PATCH = """\
diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1 +1 @@
-old
+new
"""
FAKE_MODEL_SUPPORT = """\
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from explainbench import cli
from explainbench.evaluation import service


class FakeEvaluator:
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


class InterruptingEvaluator(FakeEvaluator):
    calls = 0

    def infer(self, messages, schema):
        type(self).calls += 1
        if type(self).calls == 2:
            raise KeyboardInterrupt
        return super().infer(messages, schema)


class CountingEvaluator(FakeEvaluator):
    calls = 0

    def infer(self, messages, schema):
        type(self).calls += 1
        return super().infer(messages, schema)


class ForbiddenEvaluator:
    def __init__(self, *args, **kwargs):
        raise AssertionError("model must not be constructed")
"""


def _write_submission(
    directory: Path,
    *,
    name: str,
    submission_id: str = "clean-wheel-agent",
    with_patch: bool = False,
) -> Path:
    instance = {
        "instance_id": INSTANCE_ID,
        "explanation": "The relevant answer is described by option d.",
    }
    if with_patch:
        instance["model_patch"] = VALID_PATCH
    submission = directory / name
    submission.write_text(
        json.dumps(
            {
                "submission_id": submission_id,
                "instances": [instance],
            }
        ),
        encoding="utf-8",
    )
    return submission


def _write_effect_artifacts(
    directory: Path,
    *,
    submission_id: str,
) -> Path:
    artifacts = directory / "question-artifacts"
    context_directory = artifacts / "context"
    ground_truth_directory = artifacts / "ground_truths"
    context_directory.mkdir(parents=True)
    ground_truth_directory.mkdir(parents=True)
    contexts = {
        "e2e_effect": {
            "test_content": "assert example() == 2",
            "choices": ["passes", "fails"],
        },
        "local_effect": {
            "function_code_before_patch": "def example():\n    return 1",
            "function_parameters_before_patch": "{}",
            "line": "return 1",
            "choices": ["return value", "exception"],
            "before_or_after": "after",
        },
    }
    ground_truths = {
        "e2e_effect": {"before_answer": "a", "after_answer": "a"},
        "local_effect": {"answer": ["a"]},
    }
    for task, context in contexts.items():
        filename = f"{task}__{submission_id}.json"
        (context_directory / filename).write_text(
            json.dumps({INSTANCE_ID: context}),
            encoding="utf-8",
        )
        (ground_truth_directory / filename).write_text(
            json.dumps({INSTANCE_ID: ground_truths[task]}),
            encoding="utf-8",
        )
    return artifacts


def _run_script(
    clean_wheel: CleanWheel,
    script: str,
    *arguments: str | Path,
) -> None:
    result = clean_wheel.run_python(
        script,
        *(str(argument) for argument in arguments),
    )
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_clean_lite_evaluation_writes_result(clean_wheel: CleanWheel):
    submission = _write_submission(
        clean_wheel.run_directory,
        name="lite-submission.json",
    )
    output = clean_wheel.run_directory / "lite-result.json"

    _run_script(
        clean_wheel,
        FAKE_MODEL_SUPPORT
        + """\
service.Model = FakeEvaluator
status = cli.main([
    "evaluate",
    sys.argv[1],
    "--mode",
    "lite",
    "--model",
    "clean-wheel-fake",
    "--num-generations",
    "2",
    "--workers",
    "1",
    "--no-progress",
    "--output",
    sys.argv[2],
])
result = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert status == 0
assert result["schema_version"] == 1
assert result["selection"] == {
    "mode": "lite",
    "tasks": ["e2e.intent", "local.intent"],
}
assert all(task["counts"]["evaluated"] == 1 for task in result["tasks"].values())
assert all(not task["failures"] for task in result["tasks"].values())
assert not Path(f"{sys.argv[2]}.checkpoint.jsonl").exists()
""",
        submission,
        output,
    )


def test_clean_full_evaluation_uses_effect_artifacts(clean_wheel: CleanWheel):
    submission_id = "clean-wheel-full"
    submission = _write_submission(
        clean_wheel.run_directory,
        name="full-submission.json",
        submission_id=submission_id,
        with_patch=True,
    )
    artifacts = _write_effect_artifacts(
        clean_wheel.run_directory / "full-artifacts",
        submission_id=submission_id,
    )
    output = clean_wheel.run_directory / "full-result.json"

    _run_script(
        clean_wheel,
        FAKE_MODEL_SUPPORT
        + """\
service.Model = FakeEvaluator
status = cli.main([
    "evaluate",
    sys.argv[1],
    "--mode",
    "full",
    "--artifacts-dir",
    sys.argv[2],
    "--model",
    "clean-wheel-fake",
    "--num-generations",
    "1",
    "--workers",
    "1",
    "--no-progress",
    "--output",
    sys.argv[3],
])
result = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
assert status == 0
assert result["selection"]["tasks"] == [
    "e2e.intent",
    "e2e.effect",
    "local.intent",
    "local.effect",
]
assert set(result["tasks"]) == set(result["selection"]["tasks"])
assert all(task["counts"]["evaluated"] == 1 for task in result["tasks"].values())
assert result["tasks"]["e2e.effect"]["instances"][sys.argv[4]][
    "predictions"
] == [{"before_selection": "a", "after_selection": "a"}]
""",
        submission,
        artifacts,
        output,
        INSTANCE_ID,
    )


def test_clean_evaluation_supports_direct_task_selection(
    clean_wheel: CleanWheel,
):
    submission_id = "clean-wheel-selected"
    submission = _write_submission(
        clean_wheel.run_directory,
        name="selected-submission.json",
        submission_id=submission_id,
        with_patch=True,
    )
    artifacts = _write_effect_artifacts(
        clean_wheel.run_directory / "selected-artifacts",
        submission_id=submission_id,
    )
    output = clean_wheel.run_directory / "selected-result.json"

    _run_script(
        clean_wheel,
        FAKE_MODEL_SUPPORT
        + """\
service.Model = FakeEvaluator
status = cli.main([
    "evaluate",
    sys.argv[1],
    "--task",
    "local.intent",
    "--task",
    "e2e.effect",
    "--artifacts-dir",
    sys.argv[2],
    "--model",
    "clean-wheel-fake",
    "--num-generations",
    "1",
    "--workers",
    "1",
    "--no-progress",
    "--output",
    sys.argv[3],
])
result = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
assert status == 0
assert result["selection"] == {
    "mode": None,
    "tasks": ["local.intent", "e2e.effect"],
}
assert set(result["tasks"]) == {"local.intent", "e2e.effect"}
""",
        submission,
        artifacts,
        output,
    )


def test_clean_evaluation_resumes_compatible_checkpoint(
    clean_wheel: CleanWheel,
):
    submission = _write_submission(
        clean_wheel.run_directory,
        name="resume-submission.json",
    )
    output = clean_wheel.run_directory / "resume-result.json"

    _run_script(
        clean_wheel,
        FAKE_MODEL_SUPPORT
        + """\
arguments = [
    "evaluate",
    sys.argv[1],
    "--mode",
    "lite",
    "--model",
    "clean-wheel-fake",
    "--num-generations",
    "1",
    "--workers",
    "1",
    "--no-progress",
    "--output",
    sys.argv[2],
]
service.Model = InterruptingEvaluator
try:
    cli.main(arguments)
except KeyboardInterrupt:
    pass
else:
    raise AssertionError("evaluation was not interrupted")

checkpoint = Path(f"{sys.argv[2]}.checkpoint.jsonl")
assert checkpoint.is_file()
assert not Path(sys.argv[2]).exists()

service.Model = CountingEvaluator
stdout = StringIO()
with redirect_stdout(stdout):
    status = cli.main([*arguments, "--resume"])
result = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert status == 0
assert CountingEvaluator.calls == 1
assert "Resuming from checkpoint" in stdout.getvalue()
assert all(task["counts"]["evaluated"] == 1 for task in result["tasks"].values())
assert not checkpoint.exists()
""",
        submission,
        output,
    )


def test_clean_evaluation_rejects_incompatible_checkpoint(
    clean_wheel: CleanWheel,
):
    submission = _write_submission(
        clean_wheel.run_directory,
        name="incompatible-submission.json",
    )
    output = clean_wheel.run_directory / "incompatible-result.json"

    _run_script(
        clean_wheel,
        FAKE_MODEL_SUPPORT
        + """\
arguments = [
    "evaluate",
    sys.argv[1],
    "--mode",
    "lite",
    "--model",
    "clean-wheel-fake",
    "--num-generations",
    "1",
    "--workers",
    "1",
    "--no-progress",
    "--output",
    sys.argv[2],
]
service.Model = InterruptingEvaluator
try:
    cli.main(arguments)
except KeyboardInterrupt:
    pass
else:
    raise AssertionError("evaluation was not interrupted")

submission = Path(sys.argv[1])
payload = json.loads(submission.read_text(encoding="utf-8"))
payload["instances"][0]["explanation"] = "A changed explanation."
submission.write_text(json.dumps(payload), encoding="utf-8")

service.Model = ForbiddenEvaluator
stderr = StringIO()
with redirect_stderr(stderr):
    status = cli.main([*arguments, "--resume"])
assert status == 1
assert "checkpoint does not match" in stderr.getvalue()
assert Path(f"{sys.argv[2]}.checkpoint.jsonl").is_file()
assert not Path(sys.argv[2]).exists()
""",
        submission,
        output,
    )


def test_clean_evaluation_rejects_invalid_checkpoint(clean_wheel: CleanWheel):
    submission = _write_submission(
        clean_wheel.run_directory,
        name="invalid-checkpoint-submission.json",
    )
    output = clean_wheel.run_directory / "invalid-checkpoint-result.json"
    checkpoint = output.with_name(f"{output.name}.checkpoint.jsonl")
    checkpoint.write_text("{invalid json}\n", encoding="utf-8")

    _run_script(
        clean_wheel,
        FAKE_MODEL_SUPPORT
        + """\
service.Model = ForbiddenEvaluator
stderr = StringIO()
with redirect_stderr(stderr):
    status = cli.main([
        "evaluate",
        sys.argv[1],
        "--mode",
        "lite",
        "--model",
        "clean-wheel-fake",
        "--num-generations",
        "1",
        "--workers",
        "1",
        "--no-progress",
        "--output",
        sys.argv[2],
        "--resume",
    ])
assert status == 1
assert "invalid JSON" in stderr.getvalue()
assert Path(f"{sys.argv[2]}.checkpoint.jsonl").is_file()
assert not Path(sys.argv[2]).exists()
""",
        submission,
        output,
    )


def test_clean_evaluation_retries_failed_instance(clean_wheel: CleanWheel):
    submission = _write_submission(
        clean_wheel.run_directory,
        name="failed-instance-submission.json",
    )
    output = clean_wheel.run_directory / "failed-instance-result.json"

    _run_script(
        clean_wheel,
        FAKE_MODEL_SUPPORT
        + """\
class PartiallyFailingEvaluator(FakeEvaluator):
    def infer(self, messages, schema):
        if isinstance(messages, str) and "Masked Test:" in messages:
            raise RuntimeError("simulated provider failure")
        return super().infer(messages, schema)


arguments = [
    "evaluate",
    sys.argv[1],
    "--mode",
    "lite",
    "--model",
    "clean-wheel-fake",
    "--num-generations",
    "1",
    "--workers",
    "1",
    "--no-progress",
    "--output",
    sys.argv[2],
]
service.Model = PartiallyFailingEvaluator
status = cli.main(arguments)
checkpoint = Path(f"{sys.argv[2]}.checkpoint.jsonl")
first_result = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert status == 0
assert sum(
    task["counts"]["failed"]
    for task in first_result["tasks"].values()
) == 1
assert checkpoint.is_file()

service.Model = CountingEvaluator
status = cli.main([*arguments, "--resume"])
resumed_result = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert status == 0
assert CountingEvaluator.calls == 1
assert all(
    task["counts"]["failed"] == 0
    for task in resumed_result["tasks"].values()
)
assert not checkpoint.exists()
""",
        submission,
        output,
    )


def test_clean_model_adapter_retries_temporary_failure(
    clean_wheel: CleanWheel,
):
    _run_script(
        clean_wheel,
        """\
from types import SimpleNamespace

from explainbench.evaluation import inference
from explainbench.evaluation.inference import Model
from explainbench.evaluation.predictions import AnswerPrediction


attempts = 0


def flaky_completion(**kwargs):
    global attempts
    attempts += 1
    if attempts < 3:
        raise RuntimeError("temporary failure")
    return SimpleNamespace(
        usage=SimpleNamespace(
            completion_tokens=1,
            prompt_tokens=5,
            total_tokens=6,
        ),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content='{"answer": ["a"]}')
            )
        ],
    )


def zero_waits():
    while True:
        yield 0


inference.backoff.expo = zero_waits
inference.litellm.completion = flaky_completion
model = Model("clean-wheel-fake", max_retries=3)
prediction = model.infer_once("Choose an answer.", AnswerPrediction)
assert prediction == AnswerPrediction(answer=["a"])
assert attempts == 3
assert model.token_usage == {
    "completion_tokens": 1,
    "prompt_tokens": 5,
    "total_tokens": 6,
}
""",
    )

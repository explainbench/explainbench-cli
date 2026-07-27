"""Check the installed CLI and checker outside the source repository."""

from __future__ import annotations

import shutil

from conftest import CleanWheel


def test_clean_checker(clean_wheel: CleanWheel):
    submission = clean_wheel.run_directory / "submission-lite.json"
    shutil.copyfile(
        clean_wheel.source_root / "examples" / "submission-lite.json",
        submission,
    )

    help_result = clean_wheel.run([str(clean_wheel.executable), "--help"])
    assert help_result.returncode == 0, help_result.stderr
    assert "question-builder" in help_result.stdout
    assert "evaluate" in help_result.stdout

    checker_result = clean_wheel.run(
        [str(clean_wheel.executable), "checker", str(submission)]
    )
    assert checker_result.returncode == 0, checker_result.stderr
    assert "Submission is valid" in checker_result.stdout
    assert "Instances: 3" in checker_result.stdout

    location_result = clean_wheel.run_python(
        "import explainbench; print(explainbench.__file__)"
    )
    assert location_result.returncode == 0, location_result.stderr
    assert "site-packages" in location_result.stdout
    assert str(clean_wheel.source_root) not in location_result.stdout

    metadata_result = clean_wheel.run_python(
        """
from importlib.metadata import distribution, metadata

package_metadata = metadata("explainbench-cli")
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
print("license metadata passed")
"""
    )
    assert metadata_result.returncode == 0, metadata_result.stderr
    assert metadata_result.stdout.strip() == "license metadata passed"

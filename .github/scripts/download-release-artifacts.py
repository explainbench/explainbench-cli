"""Download and verify one wheel and source distribution from a package index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen


PACKAGE_TYPES = {
    "bdist_wheel": "wheel",
    "sdist": "sdist",
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-url", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _download(url: str, destination: Path, expected_sha256: str) -> None:
    temporary = destination.with_name(f".{destination.name}.part")
    temporary.unlink(missing_ok=True)
    digest = hashlib.sha256()

    try:
        with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        actual_sha256 = digest.hexdigest()
        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"SHA-256 mismatch for {destination.name}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    arguments = _arguments()
    metadata_url = (
        f"{arguments.index_url.rstrip('/')}/pypi/"
        f"{quote(arguments.project, safe='')}/"
        f"{quote(arguments.version, safe='')}/json"
    )
    with urlopen(metadata_url, timeout=60) as response:
        project = json.load(response)

    artifacts: dict[str, dict[str, object]] = {}
    for artifact in project["urls"]:
        package_type = artifact["packagetype"]
        if package_type in PACKAGE_TYPES:
            if package_type in artifacts:
                raise ValueError(f"multiple {package_type} artifacts found")
            artifacts[package_type] = artifact

    missing = set(PACKAGE_TYPES) - artifacts.keys()
    if missing:
        raise ValueError(f"missing package types: {sorted(missing)}")

    for package_type, directory_name in PACKAGE_TYPES.items():
        artifact = artifacts[package_type]
        filename = str(artifact["filename"])
        if Path(filename).name != filename:
            raise ValueError(f"unsafe artifact filename: {filename}")
        destination_directory = arguments.output / directory_name
        destination_directory.mkdir(parents=True, exist_ok=True)
        destination = destination_directory / filename
        _download(
            str(artifact["url"]),
            destination,
            str(artifact["digests"]["sha256"]),
        )
        print(f"downloaded and verified {destination}")


if __name__ == "__main__":
    main()

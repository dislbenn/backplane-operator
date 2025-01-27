#!/usr/bin/env python3
# Copyright (c) 2024 Red Hat, Inc.
# Copyright Contributors to the Open Cluster Management project
# Assumes: Python 3.6+

import argparse
import coloredlogs
import os
import logging
import subprocess
import shutil
import sys
import time
from pathlib import Path
from git import Repo, exc

# Configure logging with coloredlogs
coloredlogs.install(level='DEBUG')  # Set the logging level as needed

TMP_DIR = Path(__file__).resolve().parent / "tmp/dev-tools"
SCRIPTS_DIR = TMP_DIR / "scripts"
DEST_DIR = Path(__file__).resolve().parent
SUPPORTED_OPERATIONS = {
    "copy-helm-charts": {
        "script": "bundle-generation/copy-helm-charts.py",
        "args": "--destination pkg/templates/",
    },
    "helm-to-customized-helm-charts": {
        "script": "bundle-generation/helm-to-customized-helm-charts.py",
        "args": "--destination pkg/templates/",
    },
    "lint-olm-bundles-to-helm-charts": {
        "script": "./bundle-generation/olm-bundles-to-helm-charts.py",
        "args": "--destination pkg/templates/",
    },
    "olm-bundles-to-helm-charts": {
        "script": "./bundle-generation/olm-bundles-to-helm-charts.py",
        "args": "--destination pkg/templates/",
    },
    "onboard-new-components": {
        "script": "onboard-new-components.py",
        "args": "",
    },
    "sync-sha-commits": {
        "script": "./bundle-generation/sync-sha-commits.py",
        "args": "--repo {pipeline_repo} --branch {pipeline_branch}",
    },
}

def clone_repository(git_url, repo_path, branch):
    """Clones a Git repository to a specific path."""
    if os.path.exists(repo_path):
        logging.warning(f"Repository path: {repo_path} already exists. Removing existing directory.")
        shutil.rmtree(repo_path)

    logging.info(f"Cloning repository: {git_url} (branch={branch}) to {repo_path}")
    try:
        repository = Repo.clone_from(git_url, repo_path)
        repository.git.checkout(branch)
        logging.info(f"Git repository: {git_url} successfully cloned.")

    except Exception as e:
        logging.error(f"Failed to clone repository: {git_url} (branch={branch}): {e}")
        raise

def copy_scripts(script_dependencies):
    """Copies necessary scripts from the temporary directory."""
    for script in script_dependencies:
        src = SCRIPTS_DIR / script
        dest = DEST_DIR / Path(script).name

        if not src.exists():
            logging.error(f"Required script {src} not found.")
            sys.exit(1)

        shutil.copy(src, dest)
        logging.debug(f"Copied {src} to {dest}")

def cleanup_scripts(script_dependencies):
    """Cleans up copied scripts from the destination directory."""
    for script in script_dependencies:
        dest = DEST_DIR / script
        if dest.exists():
            dest.unlink(missing_ok=True)
            logging.debug(f"Removed {dest}")


def prepare_and_execute(operation, operation_data, args):
    """Prepares and executes the operation based on the provided operation data."""
    script = Path(operation_data["script"])
    script_dependencies = [script, "common.py"]
    copy_scripts(script_dependencies)

    operations_args = operation_data.get("args", "")
    if "args" in operation_data:
        operations_args = operation_data.get("args").format(
            pipeline_repo=args.pipeline_repo,
            pipeline_branch=args.pipeline_branch,
        )

    # Execute the script
    execute_script(script, operations_args)

    # Clean up the copied scripts
    cleanup_scripts(script_dependencies)

def execute_script(script, args):
    """Executes a Python script with arguments."""
    script_path = DEST_DIR / Path(script).name

    if not script_path.exists():
        logging.error(f"Script {script_path} not found.")
        sys.exit(1)

    command = ["python3", str(script_path)] + args.split()
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"Script {script} failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    finally:
        script_path.unlink(missing_ok=True)  # Clean up after execution

def main(args):
    logging.basicConfig(level=logging.INFO)

    start_time = time.time()  # Record start time
    logging.info("🔄 Initiating the generate-shell script for operator bundle management and updates.")

    # Clone the repository
    git_url = f"https://github.com/{args.org}/{args.repo}.git"
    clone_repository(git_url, TMP_DIR, args.branch)

    for operation, operation_data in SUPPORTED_OPERATIONS.items():
        if getattr(args, operation.replace("-", "_"), False):
            logging.info(f"Executing operation: {operation}")
            prepare_and_execute(operation, operation_data, args)
            break

    end_time = time.time() # Record the end time and log the duration of the script execution
    logging.info(f"Script execution took {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    # Set up argument parsing for command-line execution
    parser = argparse.ArgumentParser()

    # Define command-line arguments and their help descriptions
    for operation in SUPPORTED_OPERATIONS:
        parser.add_argument(
            f"--{operation}",
            action="store_true",
            help=f"Perform {operation.replace('-', ' ')}",
        )

    # Command-Line Arguments
    parser.add_argument("--org", help="GitHub Org name")
    parser.add_argument("--repo", help="Github Repo name")
    parser.add_argument("--branch", help="Github Repo Branch name")
    parser.add_argument("--pipeline-repo", help="Pipeline Repository name")
    parser.add_argument("--pipeline-branch", help="Pipeline Repository Branch name")

    # Set default values for unspecified arguments
    parser.set_defaults(bundle=False, commit=False, lint=False)

    # Parse command-line arguments and call the main function
    args = parser.parse_args()
    main(args)

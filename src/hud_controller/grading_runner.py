#!/usr/bin/env python3
"""
Grading runner script for agent patch testing.

This script:
1. Creates a copy of the git repo at baseline commit in /tmp
2. Applies test.patch to this repo (tests should fail)
3. Applies agent.patch to this repo (tests should pass)
4. Generates JUnit XML report at /tmp/grading_results.xml
"""

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from defusedxml import ElementTree as DefusedET

from .utils import merge_junits

logger = logging.getLogger(__name__)

class GradingRunner:
    """Handles the grading workflow for agent patch testing."""

    def __init__(
        self,
        base: str,
        test: str,
        golden: str,
    ):
        """
        Initialize the grading runner.

        Args:
            base: The baseline branch name (preferred)
            test: The test branch name (optional, for logging)
            golden: The golden branch name (optional, for logging)
        """
        # Determine what to use - branches take precedence
        self.use_base = base
        self.use_test = test
        self.use_golden = golden
        self.original_repo_path = "/home/ubuntu/example-lean-codebase"
        self.test_patch_path = "/home/root/test.patch"
        self.golden_patch_path = "/home/root/golden.patch"
        self.grade_working_dir = "/tmp/grading_workspace_" + str(uuid.uuid4())

    def _format_junit_xml(self, test_name: str, failure_message: str | None = None, stdout: str = "", stderr: str = "") -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="{test_name}" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="{test_name}" name="test{test_name}" time="0.0">
      {f"<failure type='TestFailure'>\n{failure_message}\n</failure>" if failure_message else ""}
      <system-out>\n{stdout}\n</system-out>
      <system-err>\n{stderr}\n</system-err>
    </testcase>
  </testsuite>
</testsuites>"""

    def run_tests(self) -> str:
        logger.info(f"Running tests in {self.grade_working_dir}")
        
        # [CUSTOMIZE] Set your test command here
        test_command = "lake test"
        
        result = subprocess.run(
            ["sudo", "-u", "ubuntu", "bash", "-lc", test_command],
            cwd=Path(self.grade_working_dir),
            capture_output=True,
            text=True,
        )
        
        logger.info(f"Tests completed with code: {result.returncode}")
        logger.info(f"Test output: {result.stdout}")
        logger.info(f"Test error: {result.stderr}")
        
        # # [CUSTOMIZE] Set your test results XML file path
        # xml_file = "[TEST_RESULTS_XML_FILE]"
        
        # with open(Path(self.grade_working_dir) / xml_file) as f:
        #     return f.read()

        # make a single junit xml file with the test results
        if result.returncode != 0:
            return self._format_junit_xml("Tests", "Tests failed", result.stdout, result.stderr)
        else:
            return self._format_junit_xml("Tests", None, result.stdout, result.stderr)




    def run_grading(self) -> tuple[bool, dict]:
        """Run the complete grading workflow."""
        logger.info("Starting grading workflow")
        # Step 1: Copy original repo to working dir
        logger.info(f"Copying original repo to {self.grade_working_dir}")
        subprocess.run(["sudo", "-u", "ubuntu", "cp", "-r", self.original_repo_path, self.grade_working_dir], check=True)
        logger.info(f"Copied original repo to {self.grade_working_dir}")

        # Step 2: apply test patch
        logger.info(f"Applying test patch to {self.grade_working_dir}")
        with open(self.test_patch_path) as f:
            subprocess.run(["sudo", "-u", "ubuntu", "git", "apply"], check=True, cwd=self.grade_working_dir, input=f.read().encode("utf-8"))
        logger.info(f"Applied test patch to {self.grade_working_dir}")

        # Step 3: compile the project (should work if the agent code compiles)
        logger.info(f"Compiling project in {self.grade_working_dir}")
        
        build_command = "lake build"
        
        # Run build and stream output to stderr in real-time
        build_process = subprocess.Popen(
            ["sudo", "-u", "ubuntu", "bash", "-lc", build_command],
            cwd=self.grade_working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        # Collect output for error reporting while streaming
        build_output = []
        
        def stream_build_stdout():
            """Stream stdout to stderr while collecting for error reporting."""
            for line in build_process.stdout:
                sys.stderr.write(line)
                sys.stderr.flush()
                build_output.append(line)
        
        def stream_build_stderr():
            """Stream stderr to stderr while collecting for error reporting."""
            for line in build_process.stderr:
                sys.stderr.write(line)
                sys.stderr.flush()
                build_output.append(line)
        
        # Start streaming threads
        stdout_thread = threading.Thread(target=stream_build_stdout)
        stderr_thread = threading.Thread(target=stream_build_stderr)
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for threads to complete
        stdout_thread.join()
        stderr_thread.join()
        
        # Wait for the process to complete
        build_result_code = build_process.wait()
        
        # Check exit code
        if build_result_code != 0:
            # Format compile error as JUnit XML
            xml_content = self._format_junit_xml("AgentPatchCompiles", "Agent patch compilation failed", "".join(build_output), "")
            logger.info(f"Compilation failed with exit code {build_result_code}")
            return False, {"junit": xml_content}
        
        logger.info(f"Compiled project successfully in {self.grade_working_dir}")

      
        # Step 4: Run tests
        junit_xmls = [self.run_tests()]
        
        # Cleanup: Stop server if it was started
        if self.server_process:
            logger.info("Stopping server")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.server_process.kill()

        merged_junit, full_success = merge_junits(junit_xmls)
        return full_success, {"junit": merged_junit}

    def validate_patches(self) -> tuple[bool, dict]:
        """
        Copy the original repo to a temp directory.
        Apply test patch and ensure tests fail.
        Apply golden patch and ensure tests pass.
        """
        logger.info("Starting patch validation workflow")

        # Step 1: Copy original repo to working dir
        logger.info(f"Copying original repo to {self.grade_working_dir}")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "cp", "-r", self.original_repo_path, self.grade_working_dir], check=True
        )
        logger.info(f"Copied original repo to {self.grade_working_dir}")

        # Step 2: Check that baseline compiles (without resetting)
        logger.info(f"Checking baseline compilation")
        try:
            logger.info(f"Compiling project at baseline in {self.grade_working_dir}")
            subprocess.run(
                ["sudo", "-E", "-u", "ubuntu"] + self._get_build_command(),
                cwd=self.grade_working_dir,
                timeout=1500,
                check=True,
                capture_output=True,
                text=True,
                env=dict(os.environ, HOME="/home/ubuntu"),
            )
            logger.info(f"Baseline compilation successful")
        except subprocess.CalledProcessError as e:
            # Format compile error as JUnit XML
            xml_content = self._format_junit_xml("BaselineCompiles", "Baseline compilation failed", e.stdout, e.stderr)
            logger.info(f"Baseline compilation failed, returning XML: {xml_content}")
            return False, {"junit": xml_content}

        # Step 3: Apply test patch
        logger.info(f"Applying test patch from {self.test_patch_path}")
        with open(self.test_patch_path, "r") as f:
            patch = f.read().encode("utf-8")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "apply", "-"], input=patch, check=True, cwd=self.grade_working_dir
        )
        logger.info(f"Applied test patch successfully")

        # Step 4: Ensure that the tests fail
        logger.info(f"Running tests with test patch (expecting failure)")
        result = subprocess.run(
            ["sudo", "-E", "-u", "ubuntu"] + self._get_test_command(),
            cwd=self.grade_working_dir,
            capture_output=True,
            text=True,
            env=dict(os.environ, HOME="/home/ubuntu"),
        )

        # Check both return code and actual test XML for failures
        test_xml = self._find_and_read_test_xml(self.grade_working_dir)
        has_failures = False
        
        if test_xml:
            try:
                failures, errors = self._parse_junit_xml(test_xml)
                has_failures = (failures > 0) or (errors > 0)
                logger.info(f"Test patch results: returncode={result.returncode}, failures={failures}, errors={errors}")
            except DefusedET.ParseError as e:
                logger.warning(f"Failed to parse test XML: {e}")
                # Fall back to return code check only
                has_failures = (result.returncode != 0)
        else:
            # No XML found, fall back to return code check
            has_failures = (result.returncode != 0)
        
        if not has_failures:
            # Tests passed when they should have failed (no failures in return code or XML)
            xml_content = self._format_junit_xml("TestPatchFailsTests", "Test patch did not cause tests to fail", result.stdout, result.stderr)
            logger.info(f"Tests passed with test patch (expected failure), returning XML: {xml_content}")
            return False, {"junit": xml_content}

        logger.info(f"Tests failed as expected with test patch")

        # Step 5: Reset the repo to the baseline
        logger.info(f"Resetting repo to baseline in {self.grade_working_dir}")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "reset", "--hard"], cwd=self.grade_working_dir, check=True
        )
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "clean", "-fdx"], cwd=self.grade_working_dir, check=True
        )
        logger.info(f"Reset repo to baseline successfully")

        # Step 6: Apply golden patch
        logger.info(f"Applying golden patch from {self.golden_patch_path}")
        with open(self.golden_patch_path, "r") as f:
            patch = f.read().encode("utf-8")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "apply", "-"], input=patch, check=True, cwd=self.grade_working_dir
        )
        logger.info(f"Applied golden patch successfully")

        # Step 7: Apply test patch again
        logger.info(f"Applying test patch again in {self.grade_working_dir}")
        with open(self.test_patch_path, "r") as f:
            patch = f.read().encode("utf-8")
        subprocess.run(
            ["sudo", "-u", "ubuntu", "git", "apply", "-"], input=patch, check=True, cwd=self.grade_working_dir
        )
        logger.info(f"Applied test patch again successfully")

        # Step 8: Compile with golden patch
        try:
            logger.info(f"Compiling project with golden patch in {self.grade_working_dir}")
            subprocess.run(
                ["sudo", "-E", "-u", "ubuntu"] + self._get_build_command(),
                cwd=self.grade_working_dir,
                timeout=1500,
                check=True,
                capture_output=True,
                text=True,
                env=dict(os.environ, HOME="/home/ubuntu"),
            )
            logger.info(f"Compilation with golden patch successful")
        except subprocess.CalledProcessError as e:
            # Format compile error as JUnit XML
            xml_content = self._format_junit_xml("GoldenPatchCompiles", "Golden patch compilation failed", e.stdout, e.stderr)
            logger.info(f"Golden patch compilation failed, returning XML: {xml_content}")
            return False, {"junit": xml_content}

        # Step 9: Ensure that the tests pass with golden patch
        logger.info(f"Running tests with golden patch (expecting success)")
        result = subprocess.run(
            ["sudo", "-E", "-u", "ubuntu"] + self._get_test_command(),
            cwd=self.grade_working_dir,
            capture_output=True,
            text=True,
            env=dict(os.environ, HOME="/home/ubuntu"),
        )

        # Check both return code and actual test XML for success
        test_xml = self._find_and_read_test_xml(self.grade_working_dir)
        has_failures = False
        
        if test_xml:
            try:
                failures, errors = self._parse_junit_xml(test_xml)
                has_failures = (failures > 0) or (errors > 0)
                logger.info(f"Golden patch results: returncode={result.returncode}, failures={failures}, errors={errors}")
            except DefusedET.ParseError as e:
                logger.warning(f"Failed to parse test XML: {e}")
                # Fall back to return code check only
                has_failures = (result.returncode != 0)
        else:
            # No XML found, fall back to return code check
            has_failures = (result.returncode != 0)
        
        # Check if either return code or XML shows failures
        if result.returncode != 0 or has_failures:
            # Tests failed when they should have passed
            xml_content = self._format_junit_xml(
                "GoldenPatchPassesTests", 
                f"Golden patch did not fix tests (returncode={result.returncode}, failures in XML={has_failures})", 
                result.stdout, 
                result.stderr
            )
            logger.info(f"Tests failed with golden patch (expected success), returning XML: {xml_content}")
            return False, {"junit": xml_content}

        logger.info(f"Tests passed as expected with golden patch")

        # All validation steps passed
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="PatchValidation" tests="6" failures="0" errors="0" skipped="0">
    <testcase classname="PatchValidation" name="testBaselineCompiles" time="0.0"/>
    <testcase classname="PatchValidation" name="testTestPatchApplies" time="0.0"/>
    <testcase classname="PatchValidation" name="testTestPatchFailsTests" time="0.0"/>
    <testcase classname="PatchValidation" name="testGoldenPatchApplies" time="0.0"/>
    <testcase classname="PatchValidation" name="testGoldenPatchCompiles" time="0.0"/>
    <testcase classname="PatchValidation" name="testGoldenPatchPassesTests" time="0.0"/>
  </testsuite>
</testsuites>"""

        logger.info(f"All validation steps passed")
        return True, {"junit": xml_content}

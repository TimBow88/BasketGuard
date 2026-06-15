from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"


class CiWorkflowTests(unittest.TestCase):
    def test_ci_workflow_runs_project_test_command(self) -> None:
        workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("python -m compileall packages services tests", workflow)

    def test_ci_workflow_runs_on_pull_requests_and_main_pushes(self) -> None:
        workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("pull_request:", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("- main", workflow)

    def test_ci_workflow_installs_fastapi_test_dependencies(self) -> None:
        workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("python -m pip install -r services/api/requirements.txt", workflow)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Write verification/retained-project-acceptance.json for the retained image build.

Run with the Literate AI runtime's interpreter from the project root, after any change to the
project's Component locks (the policy binds the complete selected lock tuple, so a lock refresh
makes the old file refuse with retained.acceptance.component-locks-changed):

    litai-venv/bin/python tools/retained-draft/make-acceptance-policy.py

One case per accept-action inventory entry runs the exported verifier (daemonarchy-verify,
installed into the images export by run-build-iso.sh) with the check name.  Each case pins exit
0, empty stderr and the single fixed stdout line the verifier prints on success.  The verifier
fails on any stderr text and on error patterns in the build output (see daemonarchy-verify.sh).
"""
import json
import sys
from pathlib import Path

from literate_ai.adapters.component_lock_application import current_project_component_lock_identities
from literate_ai.contracts.retained_project_acceptance import (
    RetainedProjectAcceptanceCase as Case,
    RetainedProjectAcceptancePolicy as Policy,
)
from literate_ai.projects import LoadedProject, ProjectConfigurationStore

CHECKS = ("present", "sidecar-iso", "sidecar-xz", "xz-roundtrip", "budget-raw", "budget-xz",
          "iso9660", "image-version", "image-abi", "image-tag", "live-sqlite3")
OUT = "verification/retained-project-acceptance.json"


def main():
    root = Path.cwd().resolve()
    snapshot = ProjectConfigurationStore(root).read()
    project = LoadedProject(snapshot.root, snapshot.definition)
    cases = tuple(
        Case("image:" + c, "draft-accept-image", "images/daemonarchy-verify",
             ("{output_root}/images", c), b"", 0,
             ("daemonarchy-verify image:%s OK errors=0\n" % c).encode(), b"", 300)
        for c in CHECKS)
    policy = Policy(tuple(current_project_component_lock_identities(project)), cases)
    (root / OUT).write_text(json.dumps(policy.to_dict(), indent=2) + "\n")
    print(json.dumps({"policy": OUT, "component_locks": len(policy.component_locks),
                      "cases": len(cases)}))


if __name__ == "__main__":
    sys.exit(main())

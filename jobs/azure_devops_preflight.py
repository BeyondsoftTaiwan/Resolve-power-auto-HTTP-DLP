"""Read-only Azure DevOps managed-identity readiness preflight."""
from __future__ import annotations

from fnmatch import fnmatchcase

from job.azure_devops import AzureDevOpsClient, ReviewerPolicy

BASE_BRANCH = "refs/heads/main"
EXPECTED_REPOSITORY_ID = "00c2b511-7cf2-462b-8b31-1cc0ab0a7cf3"
EXPECTED_PROJECT_ID = "e5547036-015b-4291-9a77-28151a645368"
PRIVATE_PATHS = {
    "client": "/ManualUploads/WindowsClient/WindowsClientPrivate",
    "server": "/ManualUploads/WindowsServer/WindowsServerPrivate",
    "iot": "/ManualUploads/WindowsIoT/WindowsIoTPrivate",
}


def run_azure_devops_preflight(client: AzureDevOpsClient) -> dict[str, object]:
    repository = client.get_repository()
    main = client.get_branch(BASE_BRANCH)
    path_results = {
        classification: client.path_exists(path, branch=BASE_BRANCH)
        for classification, path in PRIVATE_PATHS.items()
    }
    policies = client.list_reviewer_policies(branch=BASE_BRANCH)
    policy_counts = {
        classification: sum(
            1
            for policy in policies
            if policy.blocking
            and _policy_matches_path(policy, f"{path}/preflight.txt")
        )
        for classification, path in PRIVATE_PATHS.items()
    }
    permissions = client.evaluate_repository_permissions(
        project_id=repository.project_id,
        repository_id=repository.repository_id,
    )

    blockers: list[str] = []
    if repository.repository_id != EXPECTED_REPOSITORY_ID:
        blockers.append("repository_id_mismatch")
    if repository.project_id != EXPECTED_PROJECT_ID:
        blockers.append("project_id_mismatch")
    if repository.default_branch != BASE_BRANCH or main.name != BASE_BRANCH:
        blockers.append("main_branch_mismatch")
    blockers.extend(
        f"{classification}_path_missing"
        for classification, exists in path_results.items()
        if not exists
    )
    blockers.extend(
        f"{classification}_reviewer_policy_missing"
        for classification, count in policy_counts.items()
        if count < 1
    )
    required_permissions = {
        "read": permissions.read,
        "contribute": permissions.contribute,
        "create_branch": permissions.create_branch,
        "contribute_to_pull_requests": permissions.contribute_to_pull_requests,
    }
    blockers.extend(
        f"permission_{name}_missing"
        for name, allowed in required_permissions.items()
        if not allowed
    )
    if permissions.bypass_push_policies:
        blockers.append("bypass_push_policies_must_be_denied")
    if permissions.bypass_pull_request_policies:
        blockers.append("bypass_pull_request_policies_must_be_denied")

    return {
        "status": "READY" if not blockers else "BLOCKED",
        "repository": {
            "id": repository.repository_id,
            "project_id": repository.project_id,
            "default_branch": repository.default_branch,
            "main_commit": main.object_id,
        },
        "paths": path_results,
        "blocking_reviewer_policy_counts": policy_counts,
        "permissions": {
            **required_permissions,
            "bypass_push_policies": permissions.bypass_push_policies,
            "bypass_pull_request_policies": (
                permissions.bypass_pull_request_policies
            ),
        },
        "blockers": blockers,
        "writes_performed": False,
    }


def _policy_matches_path(
    policy: ReviewerPolicy,
    repository_path: str,
) -> bool:
    if not policy.filename_patterns:
        return True
    inclusions = [
        pattern
        for pattern in policy.filename_patterns
        if not pattern.startswith("!")
    ]
    exclusions = [
        pattern[1:]
        for pattern in policy.filename_patterns
        if pattern.startswith("!") and len(pattern) > 1
    ]
    normalized_path = repository_path.lower()
    if any(
        fnmatchcase(normalized_path, pattern.lower())
        for pattern in exclusions
    ):
        return False
    return not inclusions or any(
        fnmatchcase(normalized_path, pattern.lower())
        for pattern in inclusions
    )

"""Azure DevOps Git REST 7.1 client with managed-identity authentication."""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Mapping, Protocol, Sequence
from urllib.parse import quote

import requests
from azure.core.credentials import TokenCredential
from azure.core.exceptions import AzureError
from azure.identity import ClientAssertionCredential, ManagedIdentityCredential

from job.identity import managed_identity_client_id

API_VERSION = "7.1"
AZURE_DEVOPS_SCOPE = "https://app.vssps.visualstudio.com/.default"
TOKEN_EXCHANGE_SCOPE = "api://AzureADTokenExchange/.default"
DEFAULT_ORGANIZATION = "microsoft"
DEFAULT_PROJECT = "EPSOCopilot"
DEFAULT_REPOSITORY = "EPSOCopilot_Data"
READ_RETRY_ATTEMPTS = 3
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
REQUIRED_REVIEWERS_POLICY_TYPE_ID = "fd2167ab-b0be-447a-8ec8-39368250530e"
GIT_REPOSITORIES_NAMESPACE_ID = "2e9eb7ed-3c0a-47d4-87c1-0ffdd275fd87"
GIT_PERMISSION_BITS = {
    "read": 2,
    "contribute": 4,
    "create_branch": 16,
    "bypass_push_policies": 128,
    "contribute_to_pull_requests": 16384,
    "bypass_pull_request_policies": 32768,
}


class AzureDevOpsError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable


@dataclass(frozen=True)
class RepositoryInfo:
    repository_id: str
    project_id: str
    default_branch: str


@dataclass(frozen=True)
class BranchRef:
    name: str
    object_id: str


@dataclass(frozen=True)
class PushResult:
    branch: str
    commit_id: str


@dataclass(frozen=True)
class PullRequestResult:
    pr_id: int
    url: str
    source_branch: str
    target_branch: str
    is_draft: bool


@dataclass(frozen=True)
class ReviewerPolicy:
    policy_id: int
    filename_patterns: tuple[str, ...]
    reviewer_ids: tuple[str, ...]
    blocking: bool


@dataclass(frozen=True)
class RepositoryPermissions:
    read: bool
    contribute: bool
    create_branch: bool
    contribute_to_pull_requests: bool
    bypass_push_policies: bool
    bypass_pull_request_policies: bool


class AzureDevOpsClient(Protocol):
    def get_repository(self) -> RepositoryInfo: ...

    def get_branch(self, branch: str) -> BranchRef: ...

    def path_exists(self, repository_path: str, *, branch: str) -> bool: ...

    def get_file_content(self, repository_path: str, *, branch: str) -> bytes: ...

    def push_file(
        self,
        *,
        source_branch: str,
        base_commit: str,
        repository_path: str,
        content: bytes,
        commit_message: str,
    ) -> PushResult: ...

    def find_active_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
    ) -> PullRequestResult | None: ...

    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        is_draft: bool,
    ) -> PullRequestResult: ...

    def list_reviewer_policies(self, *, branch: str) -> Sequence[ReviewerPolicy]: ...

    def evaluate_repository_permissions(
        self,
        *,
        project_id: str,
        repository_id: str,
    ) -> RepositoryPermissions: ...


class AuthorizationProvider(Protocol):
    def authorization_header(self) -> str: ...


class HttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        **kwargs: object,
    ) -> requests.Response: ...


def _default_managed_identity_credential() -> TokenCredential:
    """Target a user-assigned identity when one is configured.

    Without an explicit client ID the credential resolves to the
    system-assigned identity, which is not necessarily the principal that was
    granted access to the downstream resource.
    """
    client_id = managed_identity_client_id()
    if client_id:
        return ManagedIdentityCredential(client_id=client_id)
    return ManagedIdentityCredential()


def _federated_credential_from_environment() -> TokenCredential:
    """Exchange a managed-identity token for an app-registration token.

    This is the secretless path across a tenant boundary. The managed identity
    and the app registration must live in the same tenant; the app registration
    is multitenant and provisioned into the tenant that backs Azure DevOps, and
    `AZDO_TENANT_ID` names that second tenant, not the identity's own.
    """
    tenant_id = os.environ.get("AZDO_TENANT_ID", "").strip()
    client_id = os.environ.get("AZDO_FEDERATED_CLIENT_ID", "").strip()
    if not tenant_id:
        raise AzureDevOpsError(
            "federated_tenant_missing",
            "AZDO_TENANT_ID must be the tenant that backs the Azure DevOps "
            "organization.",
        )
    if not client_id:
        raise AzureDevOpsError(
            "federated_client_id_missing",
            "AZDO_FEDERATED_CLIENT_ID must be the app registration's client ID.",
        )
    identity = _default_managed_identity_credential()

    def assertion() -> str:
        return identity.get_token(TOKEN_EXCHANGE_SCOPE).token

    return ClientAssertionCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        func=assertion,
    )


class ManagedIdentityAuthorization:
    """Bearer authorization from any Entra credential.

    The credential is either the managed identity directly, or — across a
    tenant boundary — a federated exchange rooted in that same identity.
    """

    def __init__(self, credential: TokenCredential | None = None):
        self._credential = credential or _default_managed_identity_credential()

    def authorization_header(self) -> str:
        try:
            token = self._credential.get_token(AZURE_DEVOPS_SCOPE)
        except AzureError as exc:
            raise AzureDevOpsError(
                "authentication_failed",
                "Could not acquire an Azure DevOps managed-identity token.",
            ) from exc
        return f"Bearer {token.token}"


class PatProofAuthorization:
    """Explicitly gated one-time proof adapter; never a production fallback."""

    def __init__(self, pat: str, *, proof_enabled: bool):
        if not proof_enabled:
            raise AzureDevOpsError(
                "pat_proof_disabled",
                "PAT authentication requires AZDO_ALLOW_PAT_PROOF=true.",
            )
        if not pat:
            raise AzureDevOpsError(
                "pat_missing",
                "AZDO_PAT is required for an explicitly enabled PAT proof.",
            )
        encoded = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
        self._header = f"Basic {encoded}"

    def authorization_header(self) -> str:
        return self._header


class AzureDevOpsRestClient:
    def __init__(
        self,
        *,
        organization: str,
        project: str,
        repository: str,
        authorization: AuthorizationProvider,
        http: HttpClient | None = None,
        timeout: tuple[float, float] = (5.0, 30.0),
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.organization = _required_segment(organization, "organization")
        self.project = _required_segment(project, "project")
        self.repository = _required_segment(repository, "repository")
        self._authorization = authorization
        self._http = http or requests.Session()
        self._timeout = timeout
        self._sleep = sleep
        self._repository_id: str | None = None
        self._base_url = (
            f"https://dev.azure.com/{quote(self.organization, safe='')}/"
            f"{quote(self.project, safe='')}"
        )
        self._repository_url = (
            f"{self._base_url}/_apis/git/repositories/"
            f"{quote(self.repository, safe='')}"
        )

    def get_repository(self) -> RepositoryInfo:
        payload = self._request_json(
            "GET",
            self._repository_url,
            params={"api-version": API_VERSION},
            expected={200},
            retry_read=True,
        )
        project = _mapping(payload.get("project"), "repository.project")
        repository = RepositoryInfo(
            repository_id=_required_string(payload, "id"),
            project_id=_required_string(project, "id"),
            default_branch=_required_string(payload, "defaultBranch"),
        )
        self._repository_id = repository.repository_id
        return repository

    def get_branch(self, branch: str) -> BranchRef:
        normalized = _branch_name(branch)
        payload = self._request_json(
            "GET",
            f"{self._repository_url}/refs",
            params={
                "filter": normalized.removeprefix("refs/"),
                "$top": 2,
                "api-version": API_VERSION,
            },
            expected={200},
            retry_read=True,
        )
        refs = _value_list(payload)
        exact = [item for item in refs if item.get("name") == normalized]
        if not exact:
            raise AzureDevOpsError(
                "branch_not_found",
                f"Azure DevOps branch does not exist: {normalized}.",
                http_status=404,
            )
        if len(exact) != 1:
            raise AzureDevOpsError(
                "ambiguous_branch",
                f"Azure DevOps returned multiple exact refs for {normalized}.",
            )
        return BranchRef(
            name=_required_string(exact[0], "name"),
            object_id=_required_string(exact[0], "objectId"),
        )

    def path_exists(self, repository_path: str, *, branch: str) -> bool:
        path = _repository_path(repository_path)
        response = self._request(
            "GET",
            f"{self._repository_url}/items",
            params={
                "path": path,
                "versionDescriptor.version": _branch_name(branch).removeprefix(
                    "refs/heads/"
                ),
                "versionDescriptor.versionType": "branch",
                "includeContent": "false",
                "api-version": API_VERSION,
            },
            expected={200, 404},
            retry_read=True,
        )
        return response.status_code == 200

    def get_file_content(self, repository_path: str, *, branch: str) -> bytes:
        path = _repository_path(repository_path)
        response = self._request(
            "GET",
            f"{self._repository_url}/items",
            params={
                "path": path,
                "versionDescriptor.version": _branch_name(branch).removeprefix(
                    "refs/heads/"
                ),
                "versionDescriptor.versionType": "branch",
                "download": "true",
                "api-version": API_VERSION,
            },
            expected={200},
            retry_read=True,
            accept="application/octet-stream",
        )
        return response.content

    def push_file(
        self,
        *,
        source_branch: str,
        base_commit: str,
        repository_path: str,
        content: bytes,
        commit_message: str,
    ) -> PushResult:
        branch = _branch_name(source_branch)
        path = _repository_path(repository_path)
        if not _is_git_object_id(base_commit):
            raise AzureDevOpsError(
                "invalid_base_commit",
                "base_commit must be a 40-character Git object ID.",
            )
        if not content:
            raise AzureDevOpsError("empty_file", "The repository file is empty.")
        if not isinstance(commit_message, str) or not commit_message.strip():
            raise AzureDevOpsError(
                "invalid_commit_message",
                "commit_message must be nonempty.",
            )

        payload = self._request_json(
            "POST",
            f"{self._repository_url}/pushes",
            params={"api-version": API_VERSION},
            json_body={
                "refUpdates": [{"name": branch, "oldObjectId": base_commit}],
                "commits": [
                    {
                        "comment": commit_message.strip(),
                        "changes": [
                            {
                                "changeType": "add",
                                "item": {"path": path},
                                "newContent": {
                                    "content": base64.b64encode(content).decode(
                                        "ascii"
                                    ),
                                    "contentType": "base64encoded",
                                },
                            }
                        ],
                    }
                ],
            },
            expected={200, 201},
            retry_read=False,
        )
        commits = payload.get("commits")
        if not isinstance(commits, list) or len(commits) != 1:
            raise AzureDevOpsError(
                "invalid_push_response",
                "Azure DevOps push response did not contain exactly one commit.",
            )
        return PushResult(
            branch=branch,
            commit_id=_required_string(_mapping(commits[0], "commit"), "commitId"),
        )

    def find_active_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
    ) -> PullRequestResult | None:
        source = _branch_name(source_branch)
        target = _branch_name(target_branch)
        payload = self._request_json(
            "GET",
            f"{self._repository_url}/pullrequests",
            params={
                "searchCriteria.sourceRefName": source,
                "searchCriteria.targetRefName": target,
                "searchCriteria.status": "active",
                "$top": 2,
                "api-version": API_VERSION,
            },
            expected={200},
            retry_read=True,
        )
        values = _value_list(payload)
        if not values:
            return None
        if len(values) != 1:
            raise AzureDevOpsError(
                "ambiguous_pull_request",
                "Multiple active pull requests use the same source and target branches.",
            )
        return self._pull_request_result(values[0])

    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        is_draft: bool,
    ) -> PullRequestResult:
        source = _branch_name(source_branch)
        target = _branch_name(target_branch)
        if not isinstance(title, str) or not title.strip():
            raise AzureDevOpsError("invalid_pr_title", "Pull request title is empty.")
        if not isinstance(description, str):
            raise AzureDevOpsError(
                "invalid_pr_description",
                "Pull request description must be a string.",
            )
        payload = self._request_json(
            "POST",
            f"{self._repository_url}/pullrequests",
            params={"api-version": API_VERSION},
            json_body={
                "sourceRefName": source,
                "targetRefName": target,
                "title": title.strip(),
                "description": description,
                "isDraft": bool(is_draft),
            },
            expected={200, 201},
            retry_read=False,
        )
        return self._pull_request_result(payload)

    def list_reviewer_policies(self, *, branch: str) -> Sequence[ReviewerPolicy]:
        normalized = _branch_name(branch)
        repository_id = self._repository_id or self.get_repository().repository_id
        values = self._paged_values(
            f"{self._base_url}/_apis/policy/configurations",
            params={"$top": 1000, "api-version": API_VERSION},
        )
        policies: list[ReviewerPolicy] = []
        for item in values:
            policy_type = item.get("type")
            settings = item.get("settings")
            if not isinstance(policy_type, Mapping) or not isinstance(
                settings,
                Mapping,
            ):
                continue
            policy_type_id = str(policy_type.get("id", "")).lower()
            display_name = str(policy_type.get("displayName", "")).lower()
            if (
                policy_type_id != REQUIRED_REVIEWERS_POLICY_TYPE_ID
                and display_name != "required reviewers"
            ):
                continue
            if item.get("isEnabled") is not True or item.get("isDeleted") is True:
                continue
            if not self._policy_applies(
                settings.get("scope"),
                normalized,
                repository_id,
            ):
                continue
            reviewer_ids = settings.get("requiredReviewerIds")
            filename_patterns = settings.get("filenamePatterns", [])
            if not isinstance(reviewer_ids, list) or not reviewer_ids:
                continue
            if not isinstance(filename_patterns, list):
                filename_patterns = []
            policies.append(
                ReviewerPolicy(
                    policy_id=_required_int(item, "id"),
                    filename_patterns=tuple(
                        value
                        for value in filename_patterns
                        if isinstance(value, str)
                    ),
                    reviewer_ids=tuple(
                        value for value in reviewer_ids if isinstance(value, str)
                    ),
                    blocking=item.get("isBlocking") is True,
                )
            )
        return tuple(policies)

    def evaluate_repository_permissions(
        self,
        *,
        project_id: str,
        repository_id: str,
    ) -> RepositoryPermissions:
        project = _required_segment(project_id, "project_id")
        repository = _required_segment(repository_id, "repository_id")
        token = f"repoV2/{project}/{repository}"
        evaluations = [
            {
                "securityNamespaceId": GIT_REPOSITORIES_NAMESPACE_ID,
                "token": token,
                "permissions": bit,
            }
            for bit in GIT_PERMISSION_BITS.values()
        ]
        payload = self._request_json(
            "POST",
            (
                f"https://dev.azure.com/{quote(self.organization, safe='')}/"
                "_apis/security/permissionevaluationbatch"
            ),
            params={"api-version": API_VERSION},
            json_body={
                "alwaysAllowAdministrators": False,
                "evaluations": evaluations,
            },
            expected={200},
            retry_read=True,
        )
        results = payload.get("evaluations")
        if not isinstance(results, list):
            raise AzureDevOpsError(
                "invalid_response",
                "Azure DevOps permission response is missing evaluations.",
            )
        by_bit: dict[int, bool] = {}
        for raw_result in results:
            result = _mapping(raw_result, "permission evaluation")
            bit = result.get("permissions")
            value = result.get("value")
            if (
                not isinstance(bit, int)
                or isinstance(bit, bool)
                or not isinstance(value, bool)
            ):
                raise AzureDevOpsError(
                    "invalid_response",
                    "Azure DevOps returned an invalid permission evaluation.",
                )
            by_bit[bit] = value
        missing = set(GIT_PERMISSION_BITS.values()) - set(by_bit)
        if missing:
            raise AzureDevOpsError(
                "invalid_response",
                "Azure DevOps omitted requested permission evaluations.",
            )
        return RepositoryPermissions(
            read=by_bit[GIT_PERMISSION_BITS["read"]],
            contribute=by_bit[GIT_PERMISSION_BITS["contribute"]],
            create_branch=by_bit[GIT_PERMISSION_BITS["create_branch"]],
            contribute_to_pull_requests=by_bit[
                GIT_PERMISSION_BITS["contribute_to_pull_requests"]
            ],
            bypass_push_policies=by_bit[
                GIT_PERMISSION_BITS["bypass_push_policies"]
            ],
            bypass_pull_request_policies=by_bit[
                GIT_PERMISSION_BITS["bypass_pull_request_policies"]
            ],
        )

    @staticmethod
    def _policy_applies(
        value: object,
        branch: str,
        repository_id: str,
    ) -> bool:
        if not isinstance(value, list):
            return False
        for raw_scope in value:
            if not isinstance(raw_scope, Mapping):
                continue
            scoped_repository_id = raw_scope.get("repositoryId")
            if scoped_repository_id not in (None, "", repository_id):
                continue
            ref_name = raw_scope.get("refName")
            if ref_name in (None, ""):
                return True
            match_kind = str(raw_scope.get("matchKind", "Exact")).lower()
            if not isinstance(ref_name, str):
                continue
            if match_kind == "exact" and branch == ref_name:
                return True
            if match_kind == "prefix" and branch.startswith(ref_name):
                return True
        return False

    def _pull_request_result(
        self,
        payload: Mapping[str, object],
    ) -> PullRequestResult:
        pr_id = _required_int(payload, "pullRequestId")
        return PullRequestResult(
            pr_id=pr_id,
            url=(
                f"{self._base_url}/_git/{quote(self.repository, safe='')}/"
                f"pullrequest/{pr_id}"
            ),
            source_branch=_required_string(payload, "sourceRefName"),
            target_branch=_required_string(payload, "targetRefName"),
            is_draft=payload.get("isDraft") is True,
        )

    def _paged_values(
        self,
        url: str,
        *,
        params: Mapping[str, object],
    ) -> list[Mapping[str, object]]:
        values: list[Mapping[str, object]] = []
        next_params = dict(params)
        while True:
            response = self._request(
                "GET",
                url,
                params=next_params,
                expected={200},
                retry_read=True,
            )
            payload = self._response_json(response)
            values.extend(_value_list(payload))
            continuation = response.headers.get("x-ms-continuationtoken")
            if not continuation:
                return values
            next_params["continuationToken"] = continuation

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, object],
        expected: set[int],
        retry_read: bool,
        json_body: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        response = self._request(
            method,
            url,
            params=params,
            expected=expected,
            retry_read=retry_read,
            json_body=json_body,
        )
        return self._response_json(response)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, object],
        expected: set[int],
        retry_read: bool,
        json_body: Mapping[str, object] | None = None,
        accept: str = "application/json",
    ) -> requests.Response:
        attempts = READ_RETRY_ATTEMPTS if retry_read else 1
        for attempt in range(1, attempts + 1):
            try:
                response = self._http.request(
                    method,
                    url,
                    params=dict(params),
                    json=dict(json_body) if json_body is not None else None,
                    headers={
                        "Accept": accept,
                        "Authorization": self._authorization.authorization_header(),
                        "Content-Type": "application/json",
                    },
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                if attempt < attempts:
                    self._sleep(float(attempt))
                    continue
                raise AzureDevOpsError(
                    "transport_error",
                    "Azure DevOps request failed before a response was received.",
                    retryable=retry_read,
                ) from exc

            if response.status_code in expected:
                return response
            retryable = response.status_code in RETRYABLE_STATUS_CODES
            if retryable and attempt < attempts:
                self._sleep(_retry_delay(response, attempt))
                continue
            raise _response_error(response, retryable=retryable)
        raise AssertionError("Azure DevOps request loop exited unexpectedly.")

    @staticmethod
    def _response_json(response: requests.Response) -> Mapping[str, object]:
        try:
            payload = response.json()
        except requests.JSONDecodeError as exc:
            raise AzureDevOpsError(
                "invalid_json_response",
                "Azure DevOps returned a non-JSON response.",
                http_status=response.status_code,
            ) from exc
        return _mapping(payload, "response")


def create_azure_devops_client_from_environment(
    *,
    http: HttpClient | None = None,
) -> AzureDevOpsRestClient:
    mode = os.environ.get("AZDO_AUTH_MODE", "managed_identity").strip().lower()
    if mode == "managed_identity":
        authorization: AuthorizationProvider = ManagedIdentityAuthorization()
    elif mode == "federated":
        authorization = ManagedIdentityAuthorization(
            _federated_credential_from_environment()
        )
    elif mode == "pat_proof":
        authorization = PatProofAuthorization(
            os.environ.get("AZDO_PAT", ""),
            proof_enabled=_is_true(os.environ.get("AZDO_ALLOW_PAT_PROOF")),
        )
    else:
        raise AzureDevOpsError(
            "invalid_auth_mode",
            "AZDO_AUTH_MODE must be managed_identity, federated, or pat_proof.",
        )
    return AzureDevOpsRestClient(
        organization=os.environ.get("AZDO_ORG", DEFAULT_ORGANIZATION),
        project=os.environ.get("AZDO_PROJECT", DEFAULT_PROJECT),
        repository=os.environ.get("AZDO_REPOSITORY", DEFAULT_REPOSITORY),
        authorization=authorization,
        http=http,
    )


@lru_cache(maxsize=1)
def get_azure_devops_client() -> AzureDevOpsRestClient:
    return create_azure_devops_client_from_environment()


def _response_error(
    response: requests.Response,
    *,
    retryable: bool,
) -> AzureDevOpsError:
    status = response.status_code
    code = {
        400: "invalid_request",
        401: "authentication_failed",
        403: "permission_denied",
        404: "not_found",
        409: "conflict",
        412: "stale_ref",
        429: "rate_limited",
    }.get(status, "service_error")
    message = {
        401: "Azure DevOps rejected the configured identity.",
        403: "The Azure DevOps identity lacks a required permission.",
        409: "Azure DevOps reported a conflicting repository operation.",
        412: "The Azure DevOps branch changed before the write completed.",
        429: "Azure DevOps rate-limited the request.",
    }.get(status, f"Azure DevOps returned HTTP {status}.")
    return AzureDevOpsError(
        code,
        message,
        http_status=status,
        retryable=retryable,
    )


def _retry_delay(response: requests.Response, attempt: int) -> float:
    raw = response.headers.get("Retry-After")
    if raw:
        try:
            return min(max(float(raw), 0.0), 10.0)
        except ValueError:
            pass
    return float(attempt)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AzureDevOpsError(
            "invalid_response",
            f"Azure DevOps response field is invalid: {field}.",
        )
    return value


def _value_list(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    value = payload.get("value")
    if not isinstance(value, list):
        raise AzureDevOpsError(
            "invalid_response",
            "Azure DevOps response does not contain a value list.",
        )
    return [_mapping(item, "value item") for item in value]


def _required_string(value: Mapping[str, object], field: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item:
        raise AzureDevOpsError(
            "invalid_response",
            f"Azure DevOps response is missing {field}.",
        )
    return item


def _required_int(value: Mapping[str, object], field: str) -> int:
    item = value.get(field)
    if not isinstance(item, int) or isinstance(item, bool):
        raise AzureDevOpsError(
            "invalid_response",
            f"Azure DevOps response is missing {field}.",
        )
    return item


def _required_segment(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AzureDevOpsError(
            f"invalid_{field}",
            f"{field} must be nonempty.",
        )
    return value.strip()


def _branch_name(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("refs/heads/"):
        raise AzureDevOpsError(
            "invalid_branch",
            "Branch must start with refs/heads/.",
        )
    if value == "refs/heads/" or any(ord(character) < 32 for character in value):
        raise AzureDevOpsError("invalid_branch", "Branch name is invalid.")
    return value


def _repository_path(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        raise AzureDevOpsError(
            "invalid_repository_path",
            "Repository path must start with '/'.",
        )
    if "\\" in value or ".." in value.split("/") or any(
        ord(character) < 32 for character in value
    ):
        raise AzureDevOpsError(
            "invalid_repository_path",
            "Repository path is unsafe.",
        )
    return value


def _is_git_object_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _is_true(value: str | None) -> bool:
    return value is not None and value.strip().lower() == "true"

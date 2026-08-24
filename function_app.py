import azure.functions as func
from azure.identity import DefaultAzureCredential
import json
import logging
import os
import requests

logger = logging.getLogger(__name__)

app = func.FunctionApp()

@app.route(
    route="GetRepositories",
    auth_level=func.AuthLevel.FUNCTION
)
def GetRepositories(req: func.HttpRequest) -> func.HttpResponse:
  logger.info("GetRepositories request received: method=%s", req.method)

  try:
    managed_identity_client_id = "f9de4e70-47fc-490a-8d58-4f65840d4e16"
    logger.info("Creating Azure credential chain")
    credential = DefaultAzureCredential(
      managed_identity_client_id=managed_identity_client_id
    )
    logger.info("Azure credential chain created")

    logger.info("Requesting Azure management access token")
    token = credential.get_token(
      "https://management.azure.com/.default"
    )
    logger.info("Azure management access token acquired")

    logger.info("Building success response payload")
    result = {
      "status": "success",
      "message": "PowerAutoDLP running",
      "token_length": len(token.token)
    }

    response = func.HttpResponse(
      json.dumps(result),
      mimetype="application/json",
      status_code=200
    )
    logger.info("GetRepositories completed: status_code=200")
    return response
  except Exception as ex:
    logger.exception("GetRepositories failed: status_code=500")
    response = func.HttpResponse(
      str(ex),
      status_code=500
    )
    logger.info("GetRepositories error response built")
    return response

@app.route(
    route="GetPullRequests",
    auth_level=func.AuthLevel.FUNCTION
)
def GetPullRequests(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("GetPullRequests received: method=%s", req.method)
    try:
        managed_identity_client_id = "f9de4e70-47fc-490a-8d58-4f65840d4e16"
        logger.info("Creating Azure credential chain")
        credential = DefaultAzureCredential(
            managed_identity_client_id=managed_identity_client_id
        )
        logger.info("Azure credential chain created")
        logger.info("Requesting Azure DevOps access token")
        token = credential.get_token(
            "499b84ac-1321-427f-aa17-267ca6975798/.default"
        )
        logger.info("Azure DevOps access token acquired")
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        url = (
            "https://dev.azure.com/"
            "microsoft/"
            "e5547036-015b-4291-9a77-28151a645368/"
            "_apis/git/repositories/"\
            "00c2b511-7cf2-462b-8b31-1cc0ab0a7cf3/"
            "pullRequests"
        )
        params = {
            "searchCriteria.status": "all",
            "$top": 100,
            "api-version": "7.1"
        }
        
        logger.info("Calling Azure DevOps Pull Request API")
        pr_response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60
        )
        logger.info(
            "Azure DevOps response status=%s",
            pr_response.status_code
        )
        if pr_response.status_code != 200:
            return func.HttpResponse(
                pr_response.text,
                mimetype="application/json",
                status_code=pr_response.status_code
            )
            data = pr_response.json()
            pull_requests = []
            for pr in data.get("value", []):
                pull_requests.append({
                    "pullRequestId": pr.get("pullRequestId"),
                    "title": pr.get("title"),
                    "status": pr.get("status"),
                    "creationDate": pr.get("creationDate"),
                    "createdBy": (
                        pr.get("createdBy", {})
                        .get("displayName")
                    ),
                    "repositoryName": (
                        pr.get("repository", {})
                        .get("name")
                    ),
                    "sourceBranch": pr.get("sourceRefName"),
                    "targetBranch": pr.get("targetRefName"),
                    "url": pr.get("url")
                })
                result = {
                    "status": "success",
                    "count": len(pull_requests),
                    "pullRequests": pull_requests
                }
                logger.info(
                    "GetPullRequests completed: count=%s",
                    len(pull_requests)
                )
                return func.HttpResponse(
                    json.dumps(result),
                    mimetype="application/json",
                    status_code=200
                )
             
    except Exception as ex:
        logger.exception("GetPullRequests failed")
        return func.HttpResponse(
            str(ex),
            status_code=500
        )

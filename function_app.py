import azure.functions as func
from azure.identity import DefaultAzureCredential
import json
import logging
import os
import requests
from datetime import datetime, timedelta

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
    logger.info(
        "GetPullRequests received: method=%s", 
        req.method
    )
    
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
            "_apis/git/repositories/"
            "00c2b511-7cf2-462b-8b31-1cc0ab0a7cf3/"
            "pullRequests"
        )

        days = int(
            req.params.get("days","180")
        )

        start_date = (
            datetime.utcnow()
            timedelta(days=days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        page_size = 100
        max_pages = 10
        max_records = 1000
        
        all_pull_requests = []
        skip = 0
        page_count = 0
        
        while page_count < max_pages:
            params = {
                "searchCriteria.status": "all",
                "searchCriteria.minTime": start_date,
                "$top": page_size,
                "$skip": skip,
                "api-version": "7.1"
            }
            logger.info(
                "Calling Azure DevOps API page=%s skip=%s",
                page_count,
                skip
            )
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
                logger.error(
                    "ADO API failed: %s",
                    pr_response.text[:500]
                )
                
                return func.HttpResponse(
                    pr_response.text,
                    mimetype="application/json",
                    status_code=pr_response.status_code
                )
                
            data = pr_response.json()
            current_page = data.get("value",[])
            if not current_page:
                logger.info(
                    "No more PRs found"
                )
                break
            for pr in current_page:
                all_pull_requests.append({
                    "pullRequestId": pr.get("pullRequestId"),
                    "title": pr.get("title"),
                    "status": pr.get("status"),
                    "creationDate": pr.get("creationDate"),
                    "closedDate": pr.get("closedDate"),
                    "createdBy": (
                        pr.get("createdBy", {})
                        .get("displayName")
                    ),
                    "repositoryName": (
                        pr.get("repository", {})
                        .get("name")
                    ),
                    "sourceBranch": pr.get(
                        "sourceRefName"
                    ),
                    "targetBranch": pr.get(
                        "targetRefName"
                    ),
                    "mergeStatus": pr.get(
                        "mergeStatus"
                    ),
                    "url": pr.get("url")
                })
            if len(current_page) < page_size:
                break
            skip += page_size
            page_count +=1
            
        result = {
            "status": "success",
            "count": len(all_pull_requests),
            "lookbackDays": days,
            "pullRequests": all_pull_requests
        }
        logger.info(
            "GetPullRequests completed: count=%s",
            len(all_pull_requests)
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


@app.route(
    route="GetFilesClientPrivateBND",
    auth_level=func.AuthLevel.FUNCTION
)
def GetFilesClientPrivateBND(req: func.HttpRequest) -> func.HttpResponse:
    
    try:
        credential = DefaultAzureCredential(
            managed_identity_client_id="f9de4e70-47fc-490a-8d58-4f65840d4e16"
        )
        token = credential.get_token(
            "499b84ac-1321-427f-aa17-267ca6975798/.default"
        )
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        url = (
            "https://dev.azure.com/microsoft/"
            "e5547036-015b-4291-9a77-28151a645368/"
            "_apis/git/repositories/"
            "00c2b511-7cf2-462b-8b31-1cc0ab0a7cf3/items"
        )
        params = {
            "scopePath": "/ManualUploads/WindowsClient/WindowsClientPrivate/Builds and Documents",
            "recursionLevel": "Full",
            "includeContentMetadata": "true",
            "api-version": "7.1"
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60
        )
        if response.status_code != 200:
            return func.HttpResponse(
                response.text,
                status_code=response.status_code
            )
        data = response.json()
        
        files = []
        
        for item in data.get("value", []):
            
            if item.get("gitObjectType") == "blob":
                
                files.append({
                    "fileName": item["path"].split("/")[-1],
                    "path": item["path"],
                    "objectId": item.get("objectId")
                })
        result = {
            "count": len(files),
            "files": files
        }
        
        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )
    except Exception as ex:
        logger.exception("GetFilesClientPrivateBND failed")
        return func.HttpResponse(
            str(ex),
            status_code=500
        )

@app.route(
    route="GetFilesClientPrivateAE",
    auth_level=func.AuthLevel.FUNCTION
)
def GetFilesClientPrivateAE(req: func.HttpRequest) -> func.HttpResponse:
    
    try:
        credential = DefaultAzureCredential(
            managed_identity_client_id="f9de4e70-47fc-490a-8d58-4f65840d4e16"
        )
        token = credential.get_token(
            "499b84ac-1321-427f-aa17-267ca6975798/.default"
        )
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        url = (
            "https://dev.azure.com/microsoft/"
            "e5547036-015b-4291-9a77-28151a645368/"
            "_apis/git/repositories/"
            "00c2b511-7cf2-462b-8b31-1cc0ab0a7cf3/items"
        )
        params = {
            "scopePath": "/ManualUploads/WindowsClient/WindowsClientPrivate/AI Experiences",
            "recursionLevel": "Full",
            "includeContentMetadata": "true",
            "api-version": "7.1"
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60
        )
        if response.status_code != 200:
            return func.HttpResponse(
                response.text,
                status_code=response.status_code
            )
        data = response.json()
        
        files = []
        
        for item in data.get("value", []):
            
            if item.get("gitObjectType") == "blob":
                
                files.append({
                    "fileName": item["path"].split("/")[-1],
                    "path": item["path"],
                    "objectId": item.get("objectId")
                })
        result = {
            "count": len(files),
            "files": files
        }
        
        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )
    except Exception as ex:
        logger.exception("GetFilesClientPrivateAE failed")
        return func.HttpResponse(
            str(ex),
            status_code=500
        )

@app.route(
    route="GetFilesClientPrivateWinHec",
    auth_level=func.AuthLevel.FUNCTION
)
def GetFilesClientPrivateWinHec(req: func.HttpRequest) -> func.HttpResponse:
    
    try:
        credential = DefaultAzureCredential(
            managed_identity_client_id="f9de4e70-47fc-490a-8d58-4f65840d4e16"
        )
        token = credential.get_token(
            "499b84ac-1321-427f-aa17-267ca6975798/.default"
        )
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        url = (
            "https://dev.azure.com/microsoft/"
            "e5547036-015b-4291-9a77-28151a645368/"
            "_apis/git/repositories/"
            "00c2b511-7cf2-462b-8b31-1cc0ab0a7cf3/items"
        )
        params = {
            "scopePath": "/ManualUploads/WindowsClient/WindowsClientPrivate/2026Client_WinHec",
            "recursionLevel": "Full",
            "includeContentMetadata": "true",
            "api-version": "7.1"
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60
        )
        if response.status_code != 200:
            return func.HttpResponse(
                response.text,
                status_code=response.status_code
            )
        data = response.json()
        
        files = []
        
        for item in data.get("value", []):
            
            if item.get("gitObjectType") == "blob":
                
                files.append({
                    "fileName": item["path"].split("/")[-1],
                    "path": item["path"],
                    "objectId": item.get("objectId")
                })
        result = {
            "count": len(files),
            "files": files
        }
        
        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )
    except Exception as ex:
        logger.exception("GetFilesClientPrivateWinHec failed")
        return func.HttpResponse(
            str(ex),
            status_code=500
        )

@app.route(
    route="GetFilesIoTPrivate",
    auth_level=func.AuthLevel.FUNCTION
)
def GetFilesIoTPrivate(req: func.HttpRequest) -> func.HttpResponse:
    
    try:
        credential = DefaultAzureCredential(
            managed_identity_client_id="f9de4e70-47fc-490a-8d58-4f65840d4e16"
        )
        token = credential.get_token(
            "499b84ac-1321-427f-aa17-267ca6975798/.default"
        )
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        url = (
            "https://dev.azure.com/microsoft/"
            "e5547036-015b-4291-9a77-28151a645368/"
            "_apis/git/repositories/"
            "00c2b511-7cf2-462b-8b31-1cc0ab0a7cf3/items"
        )
        params = {
            "scopePath": "/ManualUploads/WindowsIoT/WindowsIoTPrivate",
            "recursionLevel": "Full",
            "includeContentMetadata": "true",
            "api-version": "7.1"
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60
        )
        if response.status_code != 200:
            return func.HttpResponse(
                response.text,
                status_code=response.status_code
            )
        data = response.json()
        
        files = []
        
        for item in data.get("value", []):
            
            if item.get("gitObjectType") == "blob":
                
                files.append({
                    "fileName": item["path"].split("/")[-1],
                    "path": item["path"],
                    "objectId": item.get("objectId")
                })
        result = {
            "count": len(files),
            "files": files
        }
        
        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )
    except Exception as ex:
        logger.exception("GetFilesIoTPrivate failed")
        return func.HttpResponse(
            str(ex),
            status_code=500
        )

@app.route(
    route="GetFilesIoTPublic",
    auth_level=func.AuthLevel.FUNCTION
)
def GetFilesIoTPublic(req: func.HttpRequest) -> func.HttpResponse:
    
    try:
        credential = DefaultAzureCredential(
            managed_identity_client_id="f9de4e70-47fc-490a-8d58-4f65840d4e16"
        )
        token = credential.get_token(
            "499b84ac-1321-427f-aa17-267ca6975798/.default"
        )
        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json"
        }
        
        url = (
            "https://dev.azure.com/microsoft/"
            "e5547036-015b-4291-9a77-28151a645368/"
            "_apis/git/repositories/"
            "00c2b511-7cf2-462b-8b31-1cc0ab0a7cf3/items"
        )
        params = {
            "scopePath": "/ManualUploads/WindowsIoT/WindowsIoTPublic",
            "recursionLevel": "Full",
            "includeContentMetadata": "true",
            "api-version": "7.1"
        }
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60
        )
        if response.status_code != 200:
            return func.HttpResponse(
                response.text,
                status_code=response.status_code
            )
        data = response.json()
        
        files = []
        
        for item in data.get("value", []):
            
            if item.get("gitObjectType") == "blob":
                
                files.append({
                    "fileName": item["path"].split("/")[-1],
                    "path": item["path"],
                    "objectId": item.get("objectId")
                })
        result = {
            "count": len(files),
            "files": files
        }
        
        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200
        )
    except Exception as ex:
        logger.exception("GetFilesIoTPublic failed")
        return func.HttpResponse(
            str(ex),
            status_code=500
        )

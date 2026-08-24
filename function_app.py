import azure.functions as func
from azure.identity import DefaultAzureCredential
import json
import logging
import os

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

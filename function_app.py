import azure.functions as func
from azure.identity import ManagedIdentityCredential
import jsonn

app = func.FunctionApp()

@app.route(
    route="GetRepositories",
    auth_level=func.AzureLevel.FUNCTION
)
def GetRepositories(req: func.HttpRequest) -> func.HttpResponse:
  try:
    credential = ManagedIdentityCredential()
    token = credential.get_token(
      "https://management.azure.com/.default"
    )

    result = {
      "status": "success",
      "message": "PowerAutoDLP running",
      "token_length": len(token.token)
    }

    return func.HttpResponse(
      json.dumps(result),
      mimetype="application/json",
      status_code=200
    )
  except Exception as ex:
    return func.HttpResponse(
      str(ex),
      status_code=500
    )

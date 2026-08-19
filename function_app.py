import azure.functions as func
import json

app = func.FunctionApp()

@app.route(
route="GetRepositories",
auth_level=func.AuthLevel.FUNCTION
)
def GetRepositories(req: func.HttpRequest) -> func.HttpResponse:
 
result = {
"success": True,
"message": "PowerAutoDLP running"
}
 
return func.HttpResponse(
json.dumps(result),
mimetype="application/json",
status_code=200
)

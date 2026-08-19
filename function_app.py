import azure.functions as func
import json
 
app = func.FunctionApp()
 
@app.route(route="hello", auth_level=func.AuthLevel.FUNCTION)
def hello(req: func.HttpRequest) -> func.HttpResponse:
 
response = {
"success": True,
"message": "Azure Function is running",
"source": "Power Automate DLP Workaround"
}
 
return func.HttpResponse(
json.dumps(response),
mimetype="application/json",
status_code=200
)

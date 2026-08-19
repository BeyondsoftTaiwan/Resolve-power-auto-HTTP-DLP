import azure.functions as func
import json
 
app = func.FunctionApp()
 
@app.route(route="hello", auth_level=func.AuthLevel.FUNCTION)
def hello(req: func.HttpRequest) -> func.HttpResponse:
return func.HttpResponse(
json.dumps({
"status": "success",
"message": "Azure Function is running"
}),
mimetype="application/json",
status_code=200
)

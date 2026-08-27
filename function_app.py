import os
import json
import requests
import azure.functions as func
from azure.identity import ClientSecretCredential

@app.route(
    route="TestAdoSP",
    auth_level=func.AuthLevel.FUNCTION
)
def TestAdoSP(req: func.HttpRequest) -> func.HttpResponse:
    
    try:
        tenant_id = os.getenv(
            "ADO_TENANT_ID"
        )
        client_id = os.getenv(
            "ADO_CLIENT_ID"
        )
        
        client_secret = os.getenv(
            "ADO_CLIENT_SECRET"
        )
        
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        
        token = credential.get_token(
            "499b84ac-1321-427f-aa17-267ca6975798/.default"
        )
        
        headers = {
            "Authorization": (
                f"Bearer {token.token}"
            ),
            "Content-Type": "application/json"
        }
        url = (
            "https://app.vssps.visualstudio.com/"
            "_apis/profile/profiles/me"
            "?api-version=7.1-preview.3"
        )
        
        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )
        
        result = {
            "status_code": response.status_code,
            "response_text": response.text
        }
        
        return func.HttpResponse(
            json.dumps(
                result,
                indent=2
            ),
            mimetype="application/json",
            status_code=200
        )
    except Exception as ex:
        return func.HttpResponse(
            str(ex),
            status_code=500
        )

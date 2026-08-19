# Resolve Power Automate HTTP DLP
 
## Purpose
 
Workaround DLP restrictions that block Power Automate HTTP requests.
 
## Architecture
 
Power Automate
↓
Azure Function
↓
Azure DevOps REST API / SharePoint Graph API
↓
Azure Storage
↓
Power BI
 
## APIs
 
### GET /api/hello
 
Returns status information.
 
Example response:
{
"success": true,
"message": "Azure Function is running"
}

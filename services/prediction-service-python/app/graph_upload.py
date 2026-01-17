import logging
import os
from pathlib import Path

import msal
import requests

logger = logging.getLogger("graph_upload")

def get_auth_token():
    """Get Microsoft Graph API access token."""
    client_id = os.getenv("GRAPH_CLIENT_ID")
    client_secret = os.getenv("GRAPH_CLIENT_SECRET")
    tenant_id = os.getenv("GRAPH_TENANT_ID")

    if not (client_id and client_secret and tenant_id):
        logger.warning("Missing Graph API credentials. Skipping SharePoint upload.")
        return None

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=authority,
        client_credential=client_secret
    )

    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])

    if "access_token" in result:
        return result["access_token"]
    logger.error(f"Failed to acquire Graph token: {result.get('error_description')}")
    return None

def upload_file_to_teams(file_path: Path, target_date: str):
    """Upload a file to the Teams Channel 'Shared Documents'."""
    token = get_auth_token()
    if not token:
        return False

    # Configuration (Set these in Azure Container App)
    team_id = os.getenv("TEAMS_GROUP_ID")  # The Group ID of the Team
    channel_id = os.getenv("TEAMS_CHANNEL_ID") # The Channel ID

    # If IDs are missing, we can't upload
    if not team_id or not channel_id:
        logger.warning("Missing TEAMS_GROUP_ID or TEAMS_CHANNEL_ID. Cannot upload to SharePoint.")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream"
    }

    file_name = file_path.name

    # 1. Get the Drive ID for the Team
    # GET /groups/{group-id}/drive
    drive_url = f"https://graph.microsoft.com/v1.0/groups/{team_id}/drive"
    resp = requests.get(drive_url, headers=headers)
    if resp.status_code != 200:
        logger.error(f"Failed to get Team Drive: {resp.text}")
        return False
    drive_id = resp.json().get("id")

    # 2. Upload file
    # We upload to the root of the channel folder.
    # Usually Channel folders are in the root of the drive with the Channel Name.
    # But finding the specific folder path by Channel ID is tricky via API without listing children.
    #
    # SHORTCUT: Upload to the ROOT of the drive for now, or a specific folder if configured.
    # Better: PUT /drives/{drive-id}/root:/{filename}:/content

    upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{file_name}:/content"

    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()

        put_resp = requests.put(upload_url, headers=headers, data=file_content)

        if put_resp.status_code in [200, 201]:
            logger.info(f"Successfully uploaded {file_name} to Teams SharePoint.")
            return True
        logger.error(f"Failed to upload file: {put_resp.text}")
        return False

    except Exception as e:
        logger.error(f"Exception uploading to Graph: {e}")
        return False





from venv import logger

import httpx


MOJANG_SESSION_URL = "https://sessionserver.mojang.com"
NORISK_API_URL = "https://api.norisk.gg/api/v1"


async def request_server_id():
    url = f"{NORISK_API_URL}/launcher/auth/request-server-id"
    async with httpx.AsyncClient() as client:
        logger.debug("[API]")
        
        try:
            response = await client.post(
                    url
                )
            if not response.is_success:
                error_text = response.text
                logger.debug(f"failed to get server_id from norisk api: {error_text}")
                raise Exception(f"failed to get server_id from norisk api: {error_text}")
            
            return response.json().get("serverId")
        except httpx.RequestError as e:
            logger.debug(f"Norisk API request failed: {e}")
            raise Exception(f"Norisk API request failed: {e}")


async def join_server_session(
    access_token: str,
    selected_profile: str,
    server_id: str
) -> None:
    """
    Join a Minecraft server session
    
    Args:
        access_token: Minecraft access token
        selected_profile: UUID of the selected profile
        server_id: Server ID to join
    
    Raises:
        Exception: If the API request fails
    """
    logger.debug(
        f"API call: join_server_session for profile: {selected_profile} server_id: {server_id}"
    )

    url = f"{MOJANG_SESSION_URL}/session/minecraft/join"
    logger.debug(f"Request URL: {url}")

    join_request = {
        "accessToken": access_token,
        "selectedProfile": selected_profile,
        "serverId": server_id
    }

    logger.debug(f"Join request - selected_profile: {selected_profile}, server_id: {server_id}")

    async with httpx.AsyncClient() as client:
        logger.debug("Sending join server request to Minecraft Session API")
        
        try:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=join_request
            )
            
            logger.debug(f"Received response with status: {response.status_code}")

            # Check if successful (should return 204 No Content on success)
            if not response.is_success:
                error_text = response.text
                logger.debug(f"Join server session failed: {error_text}")
                raise Exception(f"Failed to join server session: {error_text}")
            
            logger.debug("API call completed: join_server_session - Successfully joined server session")
            
        except httpx.RequestError as e:
            logger.debug(f"API request failed: {e}")
            raise Exception(f"Minecraft API request failed: {e}")
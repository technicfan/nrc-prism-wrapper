import asyncio
import hashlib
import logging
import os
from pathlib import Path
from typing import Dict
import uuid


logger = logging.getLogger("Minecraft/Norisk API")

import aiofiles
import aiohttp
import httpx
ASSET_PATH = "NoRiskClient/assets"
MOJANG_SESSION_URL = "https://sessionserver.mojang.com"
NORISK_API_URL = "https://api.norisk.gg/api/v1"
concurrent_downloads = 10

async def download_jar(download_url,filename):
    logger = logging.getLogger("Mod Downloader")
    logger.info(f"Downloading {filename} 🙏")
    async with asyncio.Semaphore(concurrent_downloads):
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(download_url) as response:
                    response.raise_for_status()
                    async with aiofiles.open(f"./mods/{filename}", 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                        logger.info(f"Downloaded {filename} ✅")
                        return True
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                logger.exception(f"file not found: {download_url}")
                raise Exception(f"file not found: {download_url}")
            else:
                logger.exception(f"HTTP error: {e}")
                raise Exception(f"HTTP error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise Exception(f"Unexpected error: {e}")


async def download_single_asset(asset_id: str, path: str, asset_info: Dict,norisk_token: str, semaphore: asyncio.Semaphore) -> None:
        """Download a single asset file"""
        logger = logging.getLogger("Asset Downloader")
        async with semaphore:
            try:
                path_obj = Path(path)
                dir_path = path_obj.parent
                os.makedirs(f"{ASSET_PATH}/{dir_path}", exist_ok=True)
                
                # Download from CDN
                url = f"https://cdn.norisk.gg/assets/{asset_id}/assets/{path}"
                headers = {"Authorization": f"Bearer {norisk_token}"}
                logger.info(f"Downloading: {path_obj.name}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            content = await response.read()
                            
                            # Verify hash
                            downloaded_hash = hashlib.md5(content).hexdigest()
                            if downloaded_hash != asset_info.get("hash"):
                                raise ValueError(f"Hash mismatch for {path}")
                                
                            # Save file
                            async with aiofiles.open(f"{ASSET_PATH}/{path}", "wb") as f:
                                await f.write(content)
                                
                        else:
                            raise Exception(f"Failed to download {path}: {response.status}")
                            
            except Exception as e:
                print(f"Error downloading {path}: {e} URL:{url}")
                raise



async def get_asset_metadata(nrc_token,asset_id):
    url = f"https://api.norisk.gg/api/v1/launcher/pack/{asset_id}"
    headers = {
            "Authorization": f"Bearer {nrc_token}",
            "Content-Type": "application/json"
        }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Failed to fetch assets: {response.status}")
                    return {}
        except Exception as e:
            print(f"Error fetching assets: {e}")
            return {}

async def exchange_microsoft_for_minecraft_token(microsoft_access_token: str) -> tuple[str, str]:
    """
    Exchange Microsoft access token for Minecraft access token and profile UUID
    
    Returns:
        tuple: (minecraft_access_token, player_uuid)
    """
    async with httpx.AsyncClient() as client:
        # Step 1: Authenticate with Xbox Live
        xbox_auth_url = "https://user.auth.xboxlive.com/user/authenticate"
        
        xbox_payload = {
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={microsoft_access_token}"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
        
        xbox_response = await client.post(
            xbox_auth_url,
            json=xbox_payload,
            headers={"Content-Type": "application/json"}
        )
        xbox_response.raise_for_status()
        xbox_data = xbox_response.json()
        xbox_token = xbox_data["Token"]
        user_hash = xbox_data["DisplayClaims"]["xui"][0]["uhs"]

        # Step 2: Get XSTS token (Xbox Secure Token Service)
        xsts_url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        
        xsts_payload = {
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [xbox_token]
            },
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT"
        }
        
        xsts_response = await client.post(
            xsts_url,
            json=xsts_payload,
            headers={"Content-Type": "application/json"}
        )
        xsts_response.raise_for_status()
        xsts_data = xsts_response.json()
        xsts_token = xsts_data["Token"]

        # Step 3: Authenticate with Minecraft Services
        mc_auth_url = "https://api.minecraftservices.com/authentication/login_with_xbox"
        
        mc_payload = {
            "identityToken": f"XBL3.0 x={user_hash};{xsts_token}"
        }
        
        mc_response = await client.post(
            mc_auth_url,
            json=mc_payload,
            headers={"Content-Type": "application/json"}
        )
        mc_response.raise_for_status()
        mc_data = mc_response.json()
        minecraft_access_token = mc_data["access_token"]

        # Step 4: Get Minecraft profile (to get UUID)
        profile_url = "https://api.minecraftservices.com/minecraft/profile"
        
        profile_response = await client.get(
            profile_url,
            headers={"Authorization": f"Bearer {minecraft_access_token}"}
        )
        profile_response.raise_for_status()
        profile_data = profile_response.json()
        player_uuid = profile_data["id"]

        return minecraft_access_token, player_uuid

async def validate_with_norisk_api(username,server_id):
    url = f"{NORISK_API_URL}/launcher/auth/validate/v2"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                params={
                    "force": False,
                    "hwid": uuid.uuid4(),
                    "username": username,
                    "server_id": server_id
                }
            )
            if not response.is_success:
                error_text = response.text
                logger.debug(f"failed to validate server join with norisk api: {error_text}")
                raise Exception(f"failed to validate server join with norisk api: {error_text}")
            return response.json().get("value")
            
        except httpx.RequestError as e:
            logger.debug(f"API request failed: {e}")
            raise Exception(f"Norisk API request failed: {e}")


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

            if not response.is_success:
                error_text = response.text
                logger.debug(f"Join server session failed: {error_text}")
                raise Exception(f"Failed to join server session: {error_text}")
            
            logger.debug("API call completed: join_server_session - Successfully joined server session")
            
        except httpx.RequestError as e:
            logger.debug(f"API request failed: {e}")
            raise Exception(f"Minecraft API request failed: {e}")
        

async def get_norisk_versions():
    url = f"{NORISK_API_URL}/launcher/modpacks"
    async with httpx.AsyncClient() as client:
        logger.info("Getting version profiles from norisk api")
        try:
            response = await client.get(
                url
            )
            
            if not response.is_success:
                error_text = response.text
                logger.debug(f"failed to get version profiles from norisk api: {error_text}")
                raise Exception(f"failed to get version profiles from norisk api: {error_text}")
            
            return response.json()
        except httpx.RequestError as e:
            logger.debug(f"Norisk API request failed: {e}")
            raise Exception(f"Norisk API request failed: {e}")
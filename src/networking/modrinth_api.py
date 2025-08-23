
from asyncio import Semaphore
import logging
import httpx

logger = logging.getLogger("Modrinth API")


semaphore = Semaphore(10)
BASE_URL = "https://api.modrinth.com/v2"

async def get_versions(project,project_slug=None):
    url = f"{BASE_URL}/project/{project}/version"
    async with semaphore:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url
                )
                
                if not response.is_success:
                    error_text = response.text
                    if project_slug:
                        logger.info(f"failed to get versions for project {project} from modrinth api: {error_text} trying fallback")
                        # fallback to project slug if it fails(mainly for ukulib ;3 since its the only mod having the wrong projectId from the norisk api)
                        return await get_versions(project_slug)
                    else:
                        logger.exception(f"failed to get versions for project {project} from modrinth api: {error_text}")
                        return None            
                return {
                    project: response.json()
                }
            except httpx.RequestError as e:
                logger.debug(f"modrinth api request failed: {e}")
                raise Exception(f"modrinth api request failed: {e}")
            


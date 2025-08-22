import asyncio
import os
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
import aiofiles
import requests
import aiohttp

repo_url="https://maven.norisk.gg/repository/norisk-production/"

async def get_versions_from_metadata(group_id, artifact_id, repo_url=repo_url):
    group_path = group_id.replace('.', '/')
    metadata_url = urljoin(repo_url, f"{group_path}/{artifact_id}/maven-metadata.xml")
    
    try:
        async with aiohttp.ClientSession() as client:
            async with client.get(metadata_url) as response:
                response.raise_for_status()
                content = await response.read()

                loop = asyncio.get_event_loop()
                root = await loop.run_in_executor(None,ET.fromstring,content)

                versioning = root.find('versioning')
                latest = versioning.findtext('latest')
                release = versioning.findtext('release')
                last_updated = versioning.findtext('lastUpdated')
                versions_element = versioning.find('versions')
                versions = [version.text for version in versions_element.findall('version')]
                return {
                    "artifact": artifact_id,
                    "latest": latest,
                    "release": release,
                    "versions": versions,
                    "last_updated": last_updated,
                    "group": group_id
                }
        
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise Exception(f"Artifact or metadata not found: {metadata_url}")
        else:
            raise Exception(f"HTTP error: {e}")
    except ET.ParseError as e:
        raise Exception(f"Failed to parse metadata XML: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error: {e}")
    

async def download_maven_artifact( group_id, artifact_id, version, packaging='jar',repo_url=repo_url):
    """
    Download a Maven artifact from a repository
    """
    print("downloading: ",artifact_id)
    # Convert group ID to path
    group_path = group_id.replace('.', '/')
    
    filename = f"{artifact_id}-{version}"
    filename += f".{packaging}"
    
    # Build download URL
    artifact_path = f"{group_path}/{artifact_id}/{version}/{filename}"
    download_url = urljoin(repo_url, artifact_path)
    os.makedirs("./mods", exist_ok=True)
    
    try:
        async with aiohttp.ClientSession() as client:
            async with client.get(download_url) as response:
                response.raise_for_status()
                async with aiofiles.open(f"./mods/{filename}", 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            raise Exception(f"Artifact or metadata not found: {download_url}")
        else:
            raise Exception(f"HTTP error: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error: {e}")
    
    print(f"Downloaded: {filename}")
    return filename
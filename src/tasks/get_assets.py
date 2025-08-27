import asyncio
import hashlib
import logging
import os
from pathlib import Path
import networking.api as api
import config
import shutil



IGNORE_LIST = []

ASSET_PATH = "NoRiskClient/assets"


try:
    os.makedirs(ASSET_PATH,exist_ok=True)
finally:
    pass

if config.REMOVE_WATERMARK:
    IGNORE_LIST.append("nrc-cosmetics/assets/noriskclient/textures/noriskclient-logo-text.png")

concurrent_downloads = 20
async def verify_asset(path,data):

    file_path = Path(f"{ASSET_PATH}/{path}")
    if file_path.is_file():
        local_hash = await calc_hash(file_path)
        if not local_hash == data.get("hash"):
            return path, data
    else:
        return path, data


async def calc_hash(file:Path):
    '''
    Calculates the md5 hash for given path
    
    Args:
        file: path to a file
    '''
    with open(file,'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

async def main(nrc_token:str):
    '''
    Verifys and Downloads Assets

    Args:
        nrc_token: a valid noriskclient token
    '''
    logger.info("Verifying Assets")
    metadata = await api.get_asset_metadata(nrc_token,"norisk-prod")

    verify_tasks = []
    for name, asset_info in metadata.get("objects", {}).items():
        if not name in IGNORE_LIST:
            task = verify_asset(
                name,
                asset_info
            )
            verify_tasks.append(task)
    results = await asyncio.gather(*verify_tasks)
    downloads = [result for result in results if result is not None]

    semaphore = asyncio.Semaphore(concurrent_downloads)
    tasks = []
    for path, asset_data in downloads:
        task = api.download_single_asset("norisk-prod",path,asset_data,nrc_token,semaphore)
        tasks.append(task)
    logger.info("Downloading missing")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    if config.REMOVE_WATERMARK:
        shutil.copy(f"{config.WRAPPER_ROOT}/src/assets/no_watermark.png", f"{ASSET_PATH}/nrc-cosmetics/assets/noriskclient/textures/noriskclient-logo-text.png")



logger = logging.getLogger("Assets")

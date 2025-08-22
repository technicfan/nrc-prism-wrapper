import asyncio
import hashlib
import json
import os
from pathlib import Path
import networking.api as api



ASSET_PATH = "NoRiskClient/assets"
try:
    os.makedirs(ASSET_PATH,exist_ok=True)
finally:
    pass

concurrent_downloads = 10
async def verify_asset(path,data):
    file_path = Path(f"{ASSET_PATH}/{path}")
    if file_path.is_file():
        local_hash = await calc_hash(file_path)
        if not local_hash == data.get("hash"):
            return path, data
    else:
        return path, data


async def calc_hash(file:Path):
    with open(file,'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

async def main(nrc_token):
    print("Verifying Assets")
    metadata = await api.get_asset_metadata(nrc_token,"norisk-prod")

    verify_tasks = []
    for name, asset_info in metadata.get("objects", {}).items():
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
    print("Downloading missing")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(results)
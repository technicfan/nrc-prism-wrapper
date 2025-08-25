import asyncio
from asyncio.log import logger
from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
from urllib.parse import urljoin
import networking.maven as maven
import networking.api as api
import networking.modrinth_api as modrinth

@dataclass
class ModEntry():
    hash_md4 : str
    version : str
    ID : str
    filename : str
    old_file : str|None
    source_type : str
    repositoryRef : str
    groupId : str
    modrinth_id : str
    maven_id :str

async def calc_hash(file:Path):
    with open(file,'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

async def get_mc_version():
    with open("../mmc-pack.json") as f:
        mmc_pack = json.load(f)
        for component in mmc_pack.get("components"):
            if component.get("uid") == "net.minecraft":
                return component.get("version")


async def update_maven_jar(new_version,artifact,old_file):
    a = await maven.download_maven_artifact(artifact.get("group"),artifact.get("artifact"),new_version)

    if a != old_file and a != None and old_file != None:
        os.remove(f"./mods/{old_file}")
    

async def download_jar(url,filename,version:str,ID:str, old_file=None):
    print(old_file)
    a = await api.download_jar(url,filename)
    if a != old_file and a != None and old_file != None:
        os.remove(f"./mods/{old_file}")
    # stuffs thats written to index
    return {
        "id": ID,
        "hash": await calc_hash(f"./mods/{filename}"),
        "version": version
    }


async def read_index():
    try:
        with open(".nrc-index.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

async def get_installed_versions():
    index = await read_index()
    hashes = {}
    files = os.scandir("./mods")
    for f in files:
        if f.name.endswith(".jar"):
            hashes[await calc_hash(f)] = {
                "filename" : f.name
            }

    result = {}
    for entry in index:
        if entry.get("hash") in hashes:
            result[entry.get("id")] = {
                "version": entry.get("version"),
                "filename": hashes.get(entry.get("hash")).get("filename"),
                "hash":entry.get("hash")
            }
    return result


async def get_compatible_nrc_mods(mc_version):
    versions = await api.get_norisk_versions()
    prod =versions.get("packs").get("norisk-prod")
    
    mods = []

    for mod in prod.get("mods"):
        if mod.get("compatibility").get(mc_version):
                mods.append(ModEntry(
                    None,
                    mod.get("compatibility").get(mc_version).get("fabric").get("identifier"),
                    mod.get("id"),
                    None,
                    None,
                    mod.get("source").get("type"),
                    mod.get("source").get("repositoryRef"),
                    mod.get("source").get("groupId"),
                    mod.get("source").get("projectId"),
                    mod.get("source").get("artifactId")
                    ))
            
    return mods,versions.get("repositories")


async def remove_installed_mods(mods:list[ModEntry],installed_mods:dict) -> tuple[list[ModEntry],list[ModEntry]]:
    result = []
    removed = []
    for mod in mods:
        if mod.ID in installed_mods:
            if mod.version != installed_mods[mod.ID].get("version"):
                logger.info(f"Version mismatch detected installed:{installed_mods[mod.ID].get("version")} Remote Version:{mod.version}")
                mod.old_file = installed_mods[mod.ID].get("filename")
                result.append(mod)
            else:
                mod.hash_md4 = installed_mods[mod.ID].get("hash")
                removed.append(mod)
        else:
            result.append(mod)
    return result , removed

async def write_to_index_file(data:list):
    with open(".nrc-index.json","w") as f:
        json.dump(data,f,indent=2)


async def build_maven_url(artifact:ModEntry,repos):
    group_path = artifact.groupId.replace('.', '/')
    
    filename = f"{artifact.maven_id}-{artifact.version}.jar"
    artifact_path = f"{group_path}/{artifact.maven_id}/{artifact.version}/{filename}"
    return urljoin(repos.get(artifact.repositoryRef), artifact_path),filename

async def convert_to_index(mods:list[ModEntry]):
        result = []
        for mod in mods:
            result.append({
                "id": mod.ID,
                "hash": mod.hash_md4,
                "version": mod.version
            })
        return result




async def main():
    mc_version = await get_mc_version()
    mods,repos = await get_compatible_nrc_mods(mc_version)
    installed_mods = await get_installed_versions()

    mods, removed = await remove_installed_mods(mods,installed_mods)


    modrinth_api_calls = []
    download_tasks = []
    modrinth_lookup = {}


    for mod in mods:
        if mod.source_type == "modrinth":
            modrinth_lookup[mod.ID] = mod
            modrinth_lookup[mod.modrinth_id] = mod
        elif mod.source_type == "maven":
                url,filename = await build_maven_url(mod,repos)
                download_tasks.append(download_jar(url,filename,mod.version,mod.ID,mod.old_file)) 
    for mod in mods:
        if mod.source_type == "modrinth":
            modrinth_api_calls.append(modrinth.get_versions(mod.modrinth_id,mod.ID))

    results = await asyncio.gather(*modrinth_api_calls)

    for result_batch in results:
        for project_id in result_batch:
                mod = modrinth_lookup[project_id]
                for v in result_batch[project_id]:
                    if "fabric" in v.get("loaders") and mod.version == v.get("version_number"):
                        for file in v.get("files"):
                            if file.get("primary"):
                                download_tasks.append(download_jar(
                                    file.get("url"),
                                    file.get("filename"),
                                    mod.version,
                                    mod.ID,
                                    mod.old_file
                                ))
    
    if download_tasks:
        logger.info("Downloading jars")
        existing_mods_index = await convert_to_index(removed)
        index = await asyncio.gather(*download_tasks)
        
        await write_to_index_file(index+existing_mods_index)
    else:
        logger.info("No Jars need to be downloaded")

logger = logging.getLogger("Jars Geatherer")
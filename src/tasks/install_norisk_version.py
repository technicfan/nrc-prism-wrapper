import asyncio
from asyncio.log import logger
import hashlib
import json
import logging
import os
from pathlib import Path
from urllib.parse import urljoin
import networking.maven as maven
import networking.api as api
import networking.modrinth_api as modrinth


script_dir = Path(__file__).resolve().parent

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
    a = await api.download_jar(url,filename)
    if a != old_file and a != None and old_file != None:
        os.remove(f"./mods/{old_file}")
    # stuffs thats wirtten to index
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
    if not index:
        return {}
    hashes = {}
    print(index)
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
                "filename": hashes.get(entry.get("hash")).get("filename")
            }
    return result


async def get_compatible_nrc_mods(mc_version):
    versions = await api.get_norisk_versions()
    prod =versions.get("packs").get("norisk-prod")
    
    maven,modrinth = [],[]

    for mod in prod.get("mods"):
        if mod.get("compatibility").get(mc_version):
            source = mod.get("source").get("type")
            if source == "maven":
                result = {
                    "version": mod.get("compatibility").get(mc_version).get("fabric").get("identifier"),
                    "source": mod.get("source"),
                    "display_name": mod.get("displayName"),
                    "id": mod.get("id")
                    }
                maven.append(result)
            elif source == "modrinth":
                result = {
                    "version": mod.get("compatibility").get(mc_version).get("fabric").get("identifier"),
                    "source": mod.get("source"),
                    "display_name": mod.get("displayName"),
                    "id": mod.get("id")
                    }
                modrinth.append(result)
            
    return maven, modrinth ,versions.get("repositories")


async def remove_installed_mods(mods:list,installed_mods:dict):
    result = []
    removed = []
    for mod in mods:
        if mod.get("id") in installed_mods:
            print(mod.get("id"))
            if mod.get("version") != installed_mods[mod.get("id")].get("version"):
                logger.info(f"Version mismatch detected installed:{installed_mods[mod.get("id")].get("version")} Remote Version:{mod.get("version")}")
                mod["old_file"] = installed_mods[mod.get("id")].get("filename")
                result.append(mod)
            else:
                removed.append(mod)
        else:
            result.append(mod)
    return result , removed

async def write_to_index_file(data:list):
    with open(".nrc-index.json","w") as f:
        json.dump(data,f,indent=2)


async def build_maven_url(artifact,repos):
    group_path = artifact.get("source").get("groupId").replace('.', '/')
    
    filename = f"{artifact.get("source").get("artifactId")}-{artifact.get("version")}.jar"
    artifact_path = f"{group_path}/{artifact.get("source").get("artifactId")}/{artifact.get("version")}/{filename}"
    return urljoin(repos.get(artifact.get("source").get("repositoryRef")), artifact_path),filename


async def main():
    mc_version = await get_mc_version()
    maven_mods,modrinth_mods,repos = await get_compatible_nrc_mods(mc_version)
    installed_mods = await get_installed_versions()
    print(installed_mods)
    maven_mods , removed_maven = await remove_installed_mods(maven_mods,installed_mods)
    modrinth_mods, removed_modrinth = await remove_installed_mods(modrinth_mods,installed_mods)

    removed =removed_maven + removed_modrinth

    modrinth_api_calls = []
    for mod in modrinth_mods:
        modrinth_api_calls.append(modrinth.get_versions(mod.get("source").get("projectId"),mod.get("source").get("projectSlug")))
    
    results = await asyncio.gather(*modrinth_api_calls)
    download_tasks = []
    # modrinth mods
    for mod in modrinth_mods:
        for hit in results:
            if hit.get(mod.get("source").get("projectId")) or hit.get(mod.get("source").get("projectSlug")):
                result = hit.get(mod.get("source").get("projectId"))
                if not result:
                    result = hit.get(mod.get("source").get("projectSlug"))
                for r in result:
                    if "fabric" in r.get("loaders"):
                        if mod.get("version") == r.get("version_number"):
                            for f in r.get("files"):
                                if f.get("primary") == True:
                                    old_file = None
                                    if mod.get("filename"):
                                        old_file = mod.get("filename")
                                    download_tasks.append(download_jar(f.get("url"),f.get("filename"),mod.get("version"),mod.get("id"), old_file))
                                    break
    # maven mods
    for artifact in maven_mods:
        url,filename = await build_maven_url(artifact,repos)
        download_tasks.append(download_jar(url,filename,artifact.get("version"),artifact.get("id"),artifact.get("old_file")))
    

    if download_tasks:
        logger.info("Downloading jars")
        index = await asyncio.gather(*download_tasks)
        await write_to_index_file(index)
    else:
        logger.info("No Jars need to be downloaded")

logger = logging.getLogger("Jars Geatherer")
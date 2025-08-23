import asyncio
from asyncio.log import logger
import json
import logging
import os
from pathlib import Path
from urllib.parse import urljoin
import zipfile

import aiofiles
import networking.maven as maven
import networking.api as api
import networking.modrinth_api as modrinth
from packaging import version


script_dir = Path(__file__).resolve().parent


async def get_mc_version():
    with open("../mmc-pack.json") as f:
        mmc_pack = json.load(f)
        for component in mmc_pack.get("components"):
            if component.get("uid") == "net.minecraft":
                return component.get("version")

async def parse_version(version_string):
    result = {
        'mod_version': None,
        'mc_version': None,
        'original': version_string
    }
    
    # Handle format: 1.21-1.0.14 (mc_version-mod_version)
    if '-' in version_string and '+' not in version_string:
        mc_version, mod_version = version_string.split('-', 1)
        result['mod_version'] = mod_version
        result['mc_version'] = mc_version
        return result
    
    # Handle format: 1.0.30+fabric.1.21.8 (mod_version+fabric.mc_version)
    elif '+fabric.' in version_string:
        mod_version, fabric_part = version_string.split('+fabric.', 1)
        result['mod_version'] = mod_version
        result['mc_version'] = fabric_part
        return result
    
    # Handle format: 0.12.23+1.21.6 (mod_version+mc_version)
    elif '+' in version_string:
        mod_version, mc_part = version_string.split('+', 1)
        
        # Check if the mc_part starts with a digit (direct version)
        if mc_part[0].isdigit():
            result['mod_version'] = mod_version
            result['mc_version'] = mc_part
            return result
        else:
            # Handle other potential prefixes (like "forge.", "quilt.", etc.)
            first_dot = mc_part.find('.')
            if first_dot == -1:
                raise ValueError(f"Invalid version format: {version_string}")
            result['mod_version'] = mod_version
            result['mc_version'] = mc_part[first_dot + 1:]
            return result
    
    raise ValueError(f"Invalid version format: {version_string}")



async def process_artifact(remote_artifact,installed_artifacts):
    remote_versions = remote_artifact.get("versions")
    target_mc = await get_mc_version()
    filtered_versions = []
    for version in remote_versions:
        parsed_version =await parse_version(version)
        if parsed_version.get("mc_version") == target_mc:
            filtered_versions.append(parsed_version)

    print(filtered_versions)
    newest_version = filtered_versions[-1]
    matches = []
    # get installed versions
    for installed in installed_artifacts:
        if installed.get("name") == remote_artifact.get("artifact"):
            matches.append(installed)

    if matches:
        installed_version = matches[0].get("version")
        # owo lib version format workaround
        if "+" in installed_version:
            parsed = await parse_version(installed_version)
            installed_version = parsed.get("mod_version")
        
        filename = matches[0].get("filename")
        if newest_version.get("mod_version") != installed_version:
            print("NEW;",newest_version.get("mod_version"))
            print("OLD;",installed_version)
            return {
            "new_version": newest_version.get("original"),
            "artifact": remote_artifact,
            "old_file": filename
            }
    else:
        return {
            "new_version": newest_version.get("original"),
            "artifact": remote_artifact,
            "old_file": None
        }


async def update_maven_jar(new_version,artifact,old_file):
    a = await maven.download_maven_artifact(artifact.get("group"),artifact.get("artifact"),new_version)

    if a != old_file and a != None and old_file != None:
        os.remove(f"./mods/{old_file}")
    

async def download_jar(url,filename,old_file=None):
    a = await api.download_jar(url,filename)
    if a != old_file and a != None and old_file != None:
        os.remove(f"./mods/{old_file}")




async def get_installed_versions():
    installed_artifacts = {}
    files = os.scandir("./mods")
    for mod in files:
        mod_name = str(mod.name)
        if not mod_name.endswith('.jar'):
            continue
        try:
            with zipfile.ZipFile(f"./mods/{mod_name}", 'r') as jar:
                    if "fabric.mod.json" in jar.namelist():
                        with jar.open("fabric.mod.json") as f:
                            data = json.load(f)
                            installed_artifacts[data["id"]] ={
                                        "version": data["version"],
                                        "filename": mod_name
                                    }
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
            print(f"Error processing {mod_name}: {e}")
            continue
    return installed_artifacts


async def get_compatible_nrc_mods(mc_version):
    versions = await api.get_norisk_versions()
    prod =versions.get("packs").get("norisk-prod")
    
    maven,modrinth = [],[]

    for mod in prod.get("mods"):
        if mod.get("compatibility").get(mc_version):
            source = mod.get("source").get("type")
            if source == "maven":
                struct = {
                    "version": mod.get("compatibility").get(mc_version).get("fabric").get("identifier"),
                    "source": mod.get("source"),
                    "display_name": mod.get("displayName"),
                    "id": mod.get("id")
                    }
                maven.append(struct)
            elif source == "modrinth":
                struct = {
                    "version": mod.get("compatibility").get(mc_version).get("fabric").get("identifier"),
                    "source": mod.get("source"),
                    "display_name": mod.get("displayName"),
                    "id": mod.get("id")
                    }
                modrinth.append(struct)
            
    return maven, modrinth ,versions.get("repositories")


async def is_version_compatible(target_version:str, constraint:str):
    print(target_version)
    current_version = version.parse(target_version)
    min_version = version.parse(constraint.strip("=><"))
    
    if constraint.startswith('>='):
        return current_version >= min_version
    if constraint.startswith('<='):
        return current_version <= min_version
    if constraint.startswith('=='):
        return current_version == min_version
    
    return False

async def remove_installed_mods(mods:list,installed_mods:dict):
    result = []
    for mod in mods:
        if mod.get("id") in installed_mods:
            # TODO replace with an index file that tracks installed mods versions so that we avoid version parsing since some mod version formats may break with it
            mod_version = await parse_version(mod.get("version"))
            if mod_version.get("mod_version") != installed_mods[mod.get("id")].get("version"):
                logger.info(f"Version mismatch detected installed:{installed_mods[mod.get("id")].get("version")} Remote Version:{mod_version.get("mod_version")}")
                mod["old_file"] = installed_mods[mod.get("id")].get("filename")
                result.append(mod)
        else:
            result.append(mod)
    return result



async def build_maven_url(artifact,repos):
    group_path = artifact.get("source").get("groupId").replace('.', '/')
    
    filename = f"{artifact.get("source").get("artifactId")}-{artifact.get("version")}.jar"
    artifact_path = f"{group_path}/{artifact.get("source").get("artifactId")}/{artifact.get("version")}/{filename}"
    return urljoin(repos.get(artifact.get("source").get("repositoryRef")), artifact_path),filename


async def main():
    mc_version = await get_mc_version()
    maven_mods,modrinth_mods,repos = await get_compatible_nrc_mods(mc_version)
    installed_mods = await get_installed_versions()
    maven_mods = await remove_installed_mods(maven_mods,installed_mods)
    modrinth_mods = await remove_installed_mods(modrinth_mods,installed_mods)

    modrinth_api_calls = []
    for mod in modrinth_mods:
        modrinth_api_calls.append(modrinth.get_versions(mod.get("source").get("projectId"),mod.get("source").get("projectSlug")))
    
    results = await asyncio.gather(*modrinth_api_calls)
    mod_results = list(zip(modrinth_mods,results))
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
                        if mc_version in r.get("game_versions"):
                            if mod.get("version") == r.get("version_number"):
                                for f in r.get("files"):
                                    if f.get("primary") == True:
                                        old_file = None
                                        if mod.get("filename"):
                                            old_file = mod.get("filename")
                                        download_tasks.append(download_jar(f.get("url"),f.get("filename"),old_file))
                                        break
    # maven mods
    for artifact in maven_mods:
        url,filename = await build_maven_url(artifact,repos)
        download_tasks.append(download_jar(url,filename,artifact.get("old_file")))
    logger.info("Downloading jars")
    await asyncio.gather(*download_tasks)



logging.basicConfig(level=logging.INFO,format='%(asctime)s [%(levelname)s][%(name)s] %(message)s')


logger = logging.getLogger("Jars Geatherer")


asyncio.run(main())
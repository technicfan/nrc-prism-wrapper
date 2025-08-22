import asyncio
import json
import os
import zipfile

import aiofiles
import networking.maven as maven
from packaging import version

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


async def id_aliases(mod_id):
    if mod_id == "owo":
        return "owo-lib"
    return mod_id
    



async def get_installed_versions(artifacts):
    installed_artifacts = []
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
                            data["id"] = await id_aliases(data["id"])
                            if data["id"] in [artifact.get("name") for artifact in artifacts]:
                                installed_artifacts.append(
                                    {
                                        "name": data["id"],
                                        "version": data["version"],
                                        "filename": mod_name
                                    }
                                )
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
            print(f"Error processing {mod_name}: {e}")
            continue
    return installed_artifacts


async def get_repos(mc_version):
    repos = []
    with open("src/data/repos.json","r") as f:
        raw = json.load(f)
    for repo in raw:
        if await is_version_compatible(mc_version,repo.get("versions")):
            repos.append(repo)
    return repos

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

async def main():
    artifacts = await get_repos(await get_mc_version())

    maven_tasks = []

    installed_versions = await get_installed_versions(artifacts)


    for artifact in artifacts:
        maven_tasks.append(maven.get_versions_from_metadata(group_id=artifact.get("group"),artifact_id=artifact.get("name")))

    results = await asyncio.gather(*maven_tasks)
    maven_download = []
    for e in results:
        args = await process_artifact(e,installed_versions)
        if args:
            maven_download.append(update_maven_jar(args.get("new_version"),args.get("artifact"),args.get("old_file")))

    await asyncio.gather(*maven_download)
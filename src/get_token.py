import asyncio
from pathlib import Path
import api as api
import json

path = "../../../"

async def get_prsim_data(path):
    with open(f"{path}/accounts.json","r") as f:
        accounts = json.load(f)
    active = next((item for item in accounts.get("accounts") if item.get('active') == True), None)
    return active.get("msa").get("token") , active.get("profile").get("name")
    
async def write_token(token,player_uuid,path):
    if Path(f"{path} / norisk_data.json").is_file():
        with open(f"{path}/norisk_data.json", "r") as f:
            data = json.load(f)
    else:
        data = []

    entry = {
        str(player_uuid) : token
    }
    data[:] = [entry for entry in data if entry["uuid"] != player_uuid]
    data.append(entry)
    print(data)
    with open(f"{path}/norisk_data.json", "w") as f:
        f.write(json.dumps(data,indent=2)) 



async def main():
    msa_token, mc_name = await get_prsim_data(path)
    print(mc_name)
    minecraft_access_token, player_uuid = await api.exchange_microsoft_for_minecraft_token(msa_token)
    norisk_server_id = await api.request_server_id()
    await api.join_server_session(minecraft_access_token,player_uuid,norisk_server_id)
    norisk_token = await api.validate_with_norisk_api(mc_name,norisk_server_id)
    await write_token(norisk_token,player_uuid,path)
    return norisk_token
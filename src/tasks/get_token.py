from pathlib import Path
import time

import jwt
import networking.api as api
import json

path = "../../../"

async def is_token_expired(token):
    token_byte = token.encode('utf-8')
    decoded = jwt.decode(
             token_byte,
            options={"verify_signature": False},
            algorithms=["HS256", "none"]
        )
    exp_time = decoded.get('exp')
    current_time = time.time()
    if current_time > exp_time:
        print("Token is expired")
        return True
    else:
        print("Token is valid")
        return False

async def read_token_from_file(path,uuid):
    if Path(f"{path}norisk_data.json").is_file():
        with open(f"{path}norisk_data.json", "r") as f:
            data = json.load(f)
            for entry in data:
                if entry.get(uuid):
                    return entry[uuid]
async def get_prsim_data(path):
    with open(f"{path}/accounts.json","r") as f:
        accounts = json.load(f)
    active = next((item for item in accounts.get("accounts") if item.get('active') == True), None)
    return active.get("msa").get("token") , active.get("profile").get("name") , active.get("profile").get("id")
    
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
    with open(f"{path}/norisk_data.json", "w") as f:
        f.write(json.dumps(data,indent=2))



async def main():
    msa_token, mc_name, uuid = await get_prsim_data(path)
    stored_token = await read_token_from_file(path,uuid)
    if stored_token:
        if not await is_token_expired(stored_token):
            return stored_token
    minecraft_access_token, player_uuid = await api.exchange_microsoft_for_minecraft_token(msa_token)
    norisk_server_id = await api.request_server_id()
    await api.join_server_session(minecraft_access_token,player_uuid,norisk_server_id)
    norisk_token = await api.validate_with_norisk_api(mc_name,norisk_server_id)
    await write_token(norisk_token,player_uuid,path)
    return norisk_token
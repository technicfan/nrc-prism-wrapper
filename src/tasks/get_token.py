from pathlib import Path
import time
import logging
import jwt
import networking.api as api
import json
import config
path = config.PRISM_DATA_DIR
logger = logging.getLogger("Norisk Token")



async def is_token_expired(token):
    '''
    Checks if the token is expired

    Args:
        token: a noriskclient token
    
    returns:
        True|False
    '''
    token_byte = token.encode('utf-8')
    decoded = jwt.decode(
             token_byte,
            options={"verify_signature": False},
            algorithms=["HS256", "none"]
        )
    exp_time = decoded.get('exp')
    current_time = time.time()
    if current_time > exp_time:
        logger.warning("Stored Token is expired")
        return True
    else:
        logger.info("Stored Token is valid")
        return False

async def read_token_from_file(path,uuid):
    '''
    Reads the token from disk
    
    Args:
        path: path to the dir that contains norisk_data.json
        uuid: profile id
    Returns:
        Stored token for given profile id: str
    '''
    if Path(f"{path}norisk_data.json").is_file():
        with open(f"{path}norisk_data.json", "r") as f:
            data = json.load(f)
            if uuid in data:
                return data[uuid]

async def get_prsim_data(path):
    '''
    Reads Account data from accounts.json

    Args:
        path: path to the dir that contains accounts.json

    returns:
        Microsoft Account Token:str
        Minecraft IGN:str
        Profile ID:str/uuid
    '''
    with open(f"{path}/accounts.json","r") as f:
        accounts = json.load(f)
    active = next((item for item in accounts.get("accounts") if item.get('active') == True), None)
    return active.get("msa").get("token") , active.get("profile").get("name") , active.get("profile").get("id")
    
async def write_token(token:str,player_uuid,path):
    '''
    Writes given token to norisk_data.json file

    Args:
        token: norisk token to write 
        player_uuid: profile id
        path: path to the dir that contains norisk_data.json
    '''
    if Path(f"{path}/norisk_data.json").is_file():
        with open(f"{path}/norisk_data.json", "r") as f:
            data = json.load(f)
    else:
        data = {}
    data[str(player_uuid)] = token
    with open(f"{path}/norisk_data.json", "w") as f:
        f.write(json.dumps(data,indent=2))



async def main():
    '''
    Gets the norisk token via either disk or authentification

    Returns:
        norisk_token:str
    '''
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

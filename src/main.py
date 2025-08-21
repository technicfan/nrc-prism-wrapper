import asyncio
import api as api
import json

path = "../accounts.json"

async def get_prsim_data(path):
    with open(path,"r") as f:
        accounts = json.load(f)
    active = next((item for item in accounts.get("accounts") if item.get('active') == True), None)
    return active.get("msa").get("token") , active.get("profile").get("name")
    




async def main():
    msa_token, mc_name = await get_prsim_data(path)
    print(mc_name)
    minecraft_access_token, player_uuid = await api.exchange_microsoft_for_minecraft_token(msa_token)
    norisk_server_id = await api.request_server_id()
    await api.join_server_session(minecraft_access_token,player_uuid,norisk_server_id)
    await api.validate_with_norisk_api(mc_name,norisk_server_id)


if __name__ == "__main__":
    asyncio.run(main())
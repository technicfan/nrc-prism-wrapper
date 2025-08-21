import asyncio
import api as api
import json

path = "../accounts.json"

async def get_token(path):
    with open(path,"r") as f:
        accounts = json.load(f)
    active = next((item for item in accounts.get("accounts") if item.get('active') == True), None)
    return active.get("utoken").get("token")
    




async def main():
    mc_token = await get_token(path)
    await api.request_server_id()


if __name__ == "__main__":
    asyncio.run(main())
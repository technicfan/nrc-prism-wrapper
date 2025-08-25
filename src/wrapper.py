#!/usr/bin/env python3
import tasks.get_dependencies as get_dependencies
import logging
logging.basicConfig(level=logging.INFO,format='[%(asctime)s] [%(name)s/%(levelname)s] %(message)s',datefmt='%H:%M:%S')
get_dependencies.check_dependencies()


import asyncio
import os
import sys
from shutil import which
import tasks.get_token as get_token
import tasks.get_assets as get_assets
import tasks.install_norisk_version as install_norisk_version

# Wrapper script for the NoRisk instance.
# Prism Launcher will call this script with the original Java command as arguments.
# This script adds the -D property, downloads assets, mods and then runs the command.

async def download_data(token):

    tasks =[
        get_assets.main(token),
        install_norisk_version.main()

    ]
    await asyncio.gather(*tasks)

def main():
    asyncio.run(install_norisk_version.main())
    return

    # Check if the token is set. Exit with an error if it's not.
    token = asyncio.run(get_token.main())
    if not token:
        print("ERROR: Missing Norisk token", file=sys.stderr)
        sys.exit(1)

    asyncio.run(download_data(token))

    # Get the original command arguments
    original_args = sys.argv[1:]
    
    if which('obs-gamecapture') is not None:
        new_cmd = ["obs-gamecapture"]
    else:
        new_cmd = []
    
    token_added = False
    
    for arg in original_args:
        new_cmd.append(arg)
        # When we find the Java executable or main class, inject our property
        if (arg.endswith('java') or 
            arg == 'net.minecraft.client.main.Main' or 
            arg.endswith('/java') or 
            arg.endswith('\\java.exe')):
            new_cmd.append(f"-Dnorisk.token={token}")
            token_added = True
    
    if not token_added:
        new_cmd.append(f"-Dnorisk.token={token}")
    # Execute
    try:
        os.execvp(new_cmd[0], new_cmd)
    except FileNotFoundError:
        print(f"ERROR: Command not found: {new_cmd[0]}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to execute command: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
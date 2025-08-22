#!/usr/bin/env python3
import asyncio
import os
import sys
from shutil import which
import get_token
import get_assets
import geather_jars

# Wrapper script for the NoRisk instance.
# Prism Launcher will call this script with the original Java command as arguments.
# This script adds the -D property and then runs the command.

def main():
    # Check if the token is set. Exit with an error if it's not.
    token = asyncio.run(get_token.main())
    if not token:
        print("ERROR: Missing Norisk token", file=sys.stderr)
        sys.exit(1)

    asyncio.run(get_assets.main(token))
    asyncio.run(geather_jars.main())

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
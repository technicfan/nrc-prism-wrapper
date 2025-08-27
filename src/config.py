
import json5
from pathlib import Path


WRAPPER_ROOT = (Path(__file__).resolve()).parent


def get_config():


    default_config = '''\
{
    // remove the "Norisk Client" text/watermark from uis
    "remove_watermark" : true,
    // the directory this script looks for the minecraft auth token
    "prism_data_dir": "../../..",
    //TODO DOES NOT WORK CURRENTLY(force install newest mod versions) 
    "force_newest_mods": false
}
    '''

    try:
        with open(f"{WRAPPER_ROOT.parent}/config.jsonc","r") as f:
            config = json5.load(f)
    except FileNotFoundError:
        config = json5.loads(default_config)
        with open(f"{WRAPPER_ROOT.parent}/config.jsonc","w") as f:
            f.write(default_config)


    return config


c = get_config()

REMOVE_WATERMARK = c.get("remove_watermark")
PRISM_DATA_DIR = c.get("prism_data_dir")
FORCE_NEWEST_MODS = c.get("force_newest_mods")


__all__ = ["REMOVE_WATERMARK","PRISM_DATA_DIR","FORCE_NEWEST_MODS","WRAPPER_ROOT"]

import sys
import subprocess
import os
import uuid
import json
import tarfile
import shutil

from enum import Enum
from typing import List

POCKY_DIR = "/tmp"

class Cmd(Enum):
    RUN = "run"
    PULL = "pull"

def run(params: List[str]):
    print("Running:", ' '.join(params))
    result = subprocess.run(params)
    return

def build(id: str, dir_path: os.path):
    exit(0)

# Pulls and builds an image from Docker Hub. 
# Params: 
# Name (str): The name of the image to pull and build
# Tag (str): The tag to ppull and buildull
def pull(params: List[str]):
    name = params[0]
    tag = params[1]

    pull_uuid = str(uuid.uuid4())
    pull_path = os.path.join(POCKY_DIR, pull_uuid)
    os.mkdir(pull_path)
    
    subprocess.check_call(["./scripts/download-frozen-image-v2.sh", str(pull_path), f"{name}:{tag}"])

    manifest_path = os.path.join(pull_path, "manifest.json")
    with open(manifest_path) as manifest:
        manifest_json = json.loads(manifest.read())

    for manifest in manifest_json:
        for layer in manifest["Layers"]:
            layer_hash = layer.split("/")[0]

            layer_path = os.path.join(pull_path, layer_hash)
            tar_path = os.path.join(pull_path, layer)

            tar = tarfile.open(tar_path)
            tar.extractall(path=pull_path)
            tar.close()
            shutil.rmtree(layer_path)

        os.remove(os.path.join(pull_path, manifest["Config"]))

    build(pull_uuid, pull_path)

def main():
    if len(sys.argv) <= 1:
        print ("Please provide a valid command.")
        exit(0)

    cmd = sys.argv[1]
    if cmd == Cmd.RUN.value:
        run(sys.argv[2:])
    elif cmd == Cmd.PULL.value:
        pull(sys.argv[2:])
    else:
        print("Invalid command: please try again.")


if __name__ == "__main__":
   main()
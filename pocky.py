import sys
import subprocess
import os
import uuid
import json
import tarfile
import shutil

from enum import Enum
from typing import List
from bindings import overlay_mount

MANIFEST = "manifest.json"
POCKY_DIR = "./"
IMG_PREFIX = "img"
PS_PREFIX = "ps"
SRC_FILE = "src.txt"
BASE_CGROUPS = '/sys/fs/cgroup'

DEFAULT_CPU = 512
DEFAULT_MEMORY = 512 * 1000000

class Cmd(Enum):
    RUN = "run"
    PULL = "pull"
    IMAGES = "images"

def image_id_exists(id: str):
    img_dirs = [d for d in os.listdir(POCKY_DIR) if os.path.isdir(d) and d.startswith("_".join([IMG_PREFIX, id]))]
    return len(img_dirs) == 1

def run(params: List[str]): 
    img_id = params[0]
    if not image_id_exists(img_id):
        print("Provided image id does not exist.")
        exit(1)
    
    img_path = os.path.join(POCKY_DIR, '_'.join([IMG_PREFIX, img_id]))

    ps_id = '_'.join([PS_PREFIX, str(uuid.uuid4())])
    ps_path = os.path.join(POCKY_DIR, ps_id)

    fs = os.path.join(ps_path, "fs")
    mnt = os.path.join(ps_path, "fs/mnt")
    upperdir = os.path.join(ps_path, "fs/upperdir")
    workdir = os.path.join(ps_path, "fs/workdir")

    for dir in [ps_path, fs, mnt, upperdir, workdir]:
        os.mkdir(dir)

    mount_opts = f"lowerdir={str(img_path)},upperdir={str(upperdir)},workdir={str(workdir)}"
    overlay_mount(str(mnt), mount_opts)

    # Remove image files from mounted container
    for img_file in [MANIFEST, SRC_FILE, "repositories"]:
        os.path.join(mnt, img_file)

    print("Running:", ' '.join(params), "as", ps_id)

    def preexec_fn(): 
        print(os.getpid())

        # Create cgroup dirs
        for hierarchy in ["cpu", "cpuacct", "memory"]:
            cgroup = os.path.join(BASE_CGROUPS, hierarchy, ps_id)
            if not os.path.exists(cgroup):
                os.mkdir(cgroup)

            # Write current process into cgroups
            with open(f"/sys/fs/cgroup/{hierarchy}/{ps_id}/cgroup.procs", "a+") as f:
                f.write(f'{str(os.getpid())}\n')

        # Set cpu and memory limits
        with open(f"/sys/fs/cgroup/cpu/{ps_id}/cpu.shares", "w+") as f:
            f.write(f'{DEFAULT_CPU}\n')

        with open(f"/sys/fs/cgroup/memory/{ps_id}/memory.limit_in_bytes", "w+") as f:
            f.write(f'{DEFAULT_MEMORY}\n')

        os.chroot(mnt)
        os.chdir(mnt)

    result = subprocess.Popen([f"./{params[1]}"] + params[2:], preexec_fn=preexec_fn)
    result.wait()

# Lists existing images and their source
def images():
    print("Image \t\t\t\t\t Source")
    img_dirs = [d for d in os.listdir(POCKY_DIR) if os.path.isdir(d) and d.startswith(IMG_PREFIX)]
    for dir in img_dirs:
        with open(os.path.join(dir, SRC_FILE), "r") as file:
            dir_uuid = str(dir).split("_")[1]
            print(f"{dir_uuid} \t {file.read()}")

# Pulls and builds an image from Docker Hub. 
# Params: 
# Name (str): The name of the image to pull and build
# Tag (str): The tag to ppull and buildull
def pull(params: List[str]):
    name = params[0]
    tag = params[1]
    src = f"{name}:{tag}"

    pull_uuid = '_'.join([IMG_PREFIX, str(uuid.uuid4())])
    pull_path = os.path.join(POCKY_DIR, pull_uuid)
    os.mkdir(pull_path)
    
    subprocess.check_call(["./scripts/download-frozen-image-v2.sh", str(pull_path), src])

    manifest_path = os.path.join(pull_path, MANIFEST)
    with open(manifest_path) as manifest:
        manifest_json = json.loads(manifest.read())

    if len(manifest_json) > 1:
        print("Error: cannot handle more than one manifest")
        
    for layer in manifest_json[0]["Layers"]:
        layer_hash = layer.split("/")[0]

        layer_path = os.path.join(pull_path, layer_hash)
        tar_path = os.path.join(pull_path, layer)

        tar = tarfile.open(tar_path)
        tar.extractall(path=pull_path)
        tar.close()
        shutil.rmtree(layer_path)

    os.rename(os.path.join(pull_path, manifest_json[0]["Config"]), os.path.join(pull_path, "config.json"))

    with open(os.path.join(pull_path, SRC_FILE), "w") as file:
        file.write(src)

def main():
    if len(sys.argv) <= 1:
        print ("Please provide a valid command.")
        exit(0)

    cmd = sys.argv[1]
    if cmd == Cmd.RUN.value:
        run(sys.argv[2:])
    elif cmd == Cmd.PULL.value:
        pull(sys.argv[2:])
    elif cmd == Cmd.IMAGES.value:
        images()
    else:
        print("Invalid command: please try again.")


if __name__ == "__main__":
   main()
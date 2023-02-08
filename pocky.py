import sys
import subprocess
import os
import uuid
import json
import tarfile
import shutil
import signal

from enum import Enum
from typing import List
from bindings import overlay_mount, proc_mount, unshare, umount

# String constants
MANIFEST = "manifest.json"
POCKY_DIR = "./"
IMG_PREFIX = "img"
PS_PREFIX = "ps"
SRC_FILE = "src.txt"
BASE_CGROUPS = '/sys/fs/cgroup'
CONFIG = "config.json"
CMD_FILE = "cmd.txt"
PID_FILE = "pid.txt"

# Default resource limits
DEFAULT_CPU = 512
# In MB
DEFAULT_MEMORY = 512 * 1000 * 1000
DEFAULT_PIDS = 512

# Unshare flag constants
CLONE_NEWUTS = 0x04000000
CLONE_NEWPID = 0x20000000	
# NEWNS is the mount namespace
CLONE_NEWNS	= 0x00020000
CLONE_NEWIPC = 0x08000000

# Supported cpu cgroup hierarchies
HIERARCHIES = ["cpuacct", "cpu", "memory", "pids"]

class Cmd(Enum):
    RUN = "run"
    PULL = "pull"
    IMAGES = "images"
    PS = "ps"
    RM = "rm"
    RMI = "rmi"

def image_id_exists(id: str):
    img_dirs = [d for d in os.listdir(POCKY_DIR) if os.path.isdir(d) and d.startswith("_".join([IMG_PREFIX, id]))]
    return len(img_dirs) == 1

def handle_num_input(string: str):
    if not string:
        return string
    
    try:
        numeral = int(string)
        return numeral
    except ValueError:
        return None


def run(params: List[str]): 
    img_id = params[0]
    if not image_id_exists(img_id):
        print("Provided image id does not exist.")
        exit(1)
    
    # Handle user input for cpu/memory/pids
    cpu_input = handle_num_input(input("CPU shares for container (default 512):"))
    if not handle_num_input(cpu_input):
        cpu = DEFAULT_CPU
    else:
        cpu = cpu_input

    mem_input = handle_num_input(input("Memory for container in MB (default 512MB):"))
    if not handle_num_input(cpu_input):
        mem = DEFAULT_MEMORY
    else:
        mem = mem_input
    
    pid_input = handle_num_input(input("PIDs for container (default 512):"))
    if not handle_num_input(pid_input):
        pids = DEFAULT_PIDS
    else:
        pids = pid_input

    img_path = os.path.join(POCKY_DIR, '_'.join([IMG_PREFIX, img_id]))
    with open(os.path.join(img_path, CONFIG)) as f:
        config = json.loads(f.read())["config"]

    cmd = params[1:] if params[1:] else config["Cmd"]
 
    ps_id = '_'.join([PS_PREFIX, str(uuid.uuid4())])
    ps_path = os.path.join(POCKY_DIR, ps_id)

    fs = os.path.join(ps_path, "fs")
    mnt = os.path.join(ps_path, "fs/mnt")
    upperdir = os.path.join(ps_path, "fs/upperdir")
    workdir = os.path.join(ps_path, "fs/workdir")

    for dir in [ps_path, fs, mnt, upperdir, workdir]:
        os.mkdir(dir)

    # Create an overlay filesystem using the image dir as a base and an upper dir for writing changes
    mount_opts = f"lowerdir={str(img_path)},upperdir={str(upperdir)},workdir={str(workdir)}"
    overlay_mount(str(mnt), mount_opts)

    #Copy over source and cmd metadata
    shutil.copyfile(os.path.join(img_path, SRC_FILE), os.path.join(ps_path, SRC_FILE))
    with open(os.path.join(ps_path, CMD_FILE), "w+") as f:
        f.write(' '.join(cmd))

    # Remove image files from mounted container
    for img_file in [MANIFEST, SRC_FILE, CONFIG, "repositories"]:
        os.path.join(mnt, img_file)

    print("Running:", ' '.join(params), "as", ps_id)

    # Create new namespaces for process isolation
    unshare(CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWIPC | CLONE_NEWUTS)
    pid = os.fork()

    # Fork to create a new process in a new PID namespace
    if pid == 0:
        # Set env vars from config
        for env in config["Env"]:
            split_env = env.split('=', 1)
            os.environ[split_env[0]] = split_env[1]

        # Create cgroup dirs: create a cgroup dir for each hierarchy
        for hierarchy in HIERARCHIES:
            cgroup = os.path.join(BASE_CGROUPS, hierarchy, ps_id)
            if not os.path.exists(cgroup):
                os.mkdir(cgroup)

            # Write current process into each cgroup
            with open(f"/sys/fs/cgroup/{hierarchy}/{ps_id}/cgroup.procs", "a+") as f:
                f.write(f'{str(os.getpid())}\n')

        # Set cpu, memory and PID limits
        with open(f"/sys/fs/cgroup/cpu/{ps_id}/cpu.shares", "w+") as f:
            f.write(f'{cpu}\n')

        with open(f"/sys/fs/cgroup/memory/{ps_id}/memory.limit_in_bytes", "w+") as f:
            f.write(f'{mem}\n')

        with open(f"/sys/fs/cgroup/pids/{ps_id}/pids.max", "w+") as f:
            f.write(f'{pids}\n')

        # Isolate process by changing its root to be the mount point
        os.chroot(mnt)

        # Change dir to be either the root or the working dir of the image
        if config["WorkingDir"]:
            os.chdir(config["WorkingDir"])
        else:
            os.chdir(mnt)

        # Mount the proc filesystem
        if not os.path.isdir("/proc"):
            os.mkdir("/proc")
        proc_mount()

        # Execute the cmd
        os.execvp(cmd[0], cmd)
    else:
        # Write the pid of the forked process so it can be killed if neccessary
        with open(os.path.join(ps_path, PID_FILE), "w+") as file:
            file.write(str(pid))

        os.wait()
        # Clean-up resources and exit
        rm(ps_id.split("_")[1], suppress_output=True)

# Removes a running container.
# Suppresses output if called as part of run clean-up
def rm(id: str, suppress_output: bool = False):
    ps_id = f'ps_{id}'
    ps_dir = os.path.join(POCKY_DIR, f'ps_{id}')
    if not os.path.isdir(ps_dir):
        if not suppress_output:
            print("Provided container does not exist.")
        exit(1)

    try:
        with open(os.path.join(ps_dir, PID_FILE), "r+") as file:
            process_pid = int(file.read())

            # Kill the process if it is still running
            # TODO doesn't handle processes that handle SIGTERM (-f flag)
            try:
                os.kill(process_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        # Umount the proc directory so that the overlay mount dir can be unmounted
        umount(os.path.join(ps_dir, "fs/mnt/proc"))
        umount(os.path.join(ps_dir, "fs/mnt"))
        
        # Remove cgroup hierarchies (cpu + cpuacct are removed together)
        for hierarchy in HIERARCHIES[1:]:
            os.rmdir(os.path.join(BASE_CGROUPS, hierarchy, ps_id))
        shutil.rmtree(ps_dir)
    
    # If there was an error, it is either unexpected,
    # it is because the container was ended manually and this is
    # being called from run(), or because the process was not killed
    except OSError as e:
        if not suppress_output:
            print("There was an error deleting " + id)
        return

# Deletes an existing image
def rmi(id: str):
    id_dir = os.path.join(POCKY_DIR, f'img_{id}')
    if not os.path.isdir(id_dir):
        print("Provided image does not exist.")
        exit(1)

    shutil.rmtree(id_dir)

def ps():
    print(f'{"Container Id" :<40} {"Image" :<30} {"Cmd" :<30}')
    # Get all ps dirs
    ps_dirs = [d for d in os.listdir(POCKY_DIR) if os.path.isdir(d) and d.startswith(PS_PREFIX)]
    for ps_dir in ps_dirs:
        # For each ps dir: check if the associated cgroup still has a running process
        with open(os.path.join(BASE_CGROUPS, "cpu", ps_dir, "cgroup.procs"), "r") as f:
            contents = f.read()
    
        # If it does, get the metadata from the ps dir and print
        if contents:
            container_id = ps_dir.split("_")[1]
            with open(os.path.join(ps_dir, SRC_FILE), "r") as f:
                image = f.read()
            with open(os.path.join(ps_dir, CMD_FILE), "r") as f:
                cmd = f.read()
            print(f'{container_id :<40} {image :<30} {cmd :<30}')

# Lists existing images and their source
def images():
    print("Container \t\t\t\t\t Image \t")
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

    os.rename(os.path.join(pull_path, manifest_json[0]["Config"]), os.path.join(pull_path, CONFIG))

    with open(os.path.join(pull_path, SRC_FILE), "w+") as file:
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
    elif cmd == Cmd.PS.value:
        ps()
    elif cmd == Cmd.RM.value:
        rm(sys.argv[2])
    elif cmd == Cmd.RMI.value:
        rmi(sys.argv[2])
    else:
        print("Invalid command: please try again.")


if __name__ == "__main__":
   main()
import sys
import subprocess

from enum import Enum
from typing import List

class Cmd(Enum):
    RUN = "run"

def run(params: List[str]):
    print("Running:", ' '.join(params))
    result = subprocess.run(params)
    return

def main():
    cmd = sys.argv[1]
    if cmd == Cmd.RUN.value:
        run(sys.argv[2:])
    else:
        print("Invalid command: please try again.")


if __name__ == "__main__":
   main()
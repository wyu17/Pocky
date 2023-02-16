# Pocky
![image](https://user-images.githubusercontent.com/62117275/218774398-d3ab344b-9fe2-40db-ba05-7875d4cac8bf.png)

Implements the core functionality of the Docker container runtime using Python and Linux kernel primitives.

Pocky has no Python dependencies, but makes heavy use of Linux syscalls.

Inspired by [Bocker](https://github.com/p8952/bocker) and [Gocker](https://github.com/shuveb/containers-the-hard-way).

## Implemented Functionality

* Resource isolation (namespaces)
* Filesystem isolation (mount namespace, chroot)
* CPU / Memory / PID resource limitation (cgroups v1)
* Networking (container -> outside world, host <--> container, container < -- > container)
* (Some) support for image configuration: `workdir`, `env` and `cmd`
* `docker pull` (with DockerHub compatibility!)
* `docker images`
* `docker ps`
* `docker run`
* `docker rmi`

## System Prerequisites

For executing Pocky:
* Python 3.6+

For pulling images:
* go
* jq
* curl

For networking:
* iptables

Tested on Ubuntu 18.04: may not work out of the box on other distributions.

**Note:** If running Pocky, it is recommended to run it in a virtual machine. 
Pocky must be run as root, and will arbitarily modify the file system and host networking stack. 

Additionally, Pocky may not work correctly if there are pre-existing ip routing rules with a higher priority than Pocky's routing rules. 

## Example Usage

### Pulling Images
```
$ python3 pocky.py pull hello-world latest
Pulling....
Successfully pulled image hello-world:latest.

$ python3 pocky.py pull centos 7
Pulling....
Successfully pulled image centos:7.

$ python3 pocky.py images
Container                                        Image 
abc1c8ea-fb14-4061-962e-29db04942ccf     hello-world:latest
fad3cb34-e613-42f5-b863-52c9967b2040     centos:7
```

### Run Hello World
```
$ python3 pocky.py run abc1c8ea-fb14-4061-962e-29db04942ccf
CPU shares for container (default 512):
Memory for container in MB (default 512MB):
PIDs for container (default 512):
Running: abc1c8ea-fb14-4061-962e-29db04942ccf as ps_0caf1e1a-2eab-4c09-9e05-b5b6b72e5219 on IP 10.0.0.140

Hello from Docker!
This message shows that your installation appears to be working correctly.

To generate this message, Docker took the following steps:
 1. The Docker client contacted the Docker daemon.
 2. The Docker daemon pulled the "hello-world" image from the Docker Hub.
    (amd64)
 3. The Docker daemon created a new container from that image which runs the
    executable that produces the output you are currently reading.
 4. The Docker daemon streamed that output to the Docker client, which sent it
    to your terminal.

To try something more ambitious, you can run an Ubuntu container with:
 $ docker run -it ubuntu bash

Share images, automate workflows, and more with a free Docker ID:
 https://hub.docker.com/

For more examples and ideas, visit:
 https://docs.docker.com/get-started/
```

### Run a Shell
```
$ python3 pocky.py run fad3cb34-e613-42f5-b863-52c9967b2040
CPU shares for container (default 512):
Memory for container in MB (default 512MB): 30
PIDs for container (default 512): 2
Running: fad3cb34-e613-42f5-b863-52c9967b2040 as ps_eaaa7b2d-cb47-411b-a21d-92468d6077d0 on IP 10.0.0.13
bash-4.2# ps
  PID TTY          TIME CMD
    1 ?        00:00:00 bash
   12 ?        00:00:00 ps
```

### Memory Restriction

Script Source: [Hechao Li](https://hechao.li/2020/07/09/Mini-Container-Series-Part-6-Limit-Memory-Usage/)
```
bash-4.2# cat eater.py
import time
a = []
i = 0
while True:
    i += 1
    a.append(' ' * 10 * 1024 * 1024)
    print('Ate {} MB'.format(i * 10))
    time.sleep(1)
bash-4.2# python eater.py
Ate 10 MB
Ate 20 MB
Killed
bash-4.2# 
```

### PID restriction
```
bash-4.2# /bin/bash
bash-4.2# /bin/bash
bash: fork: retry: No child processes
bash: fork: retry: No child processes
bash: fork: retry: No child processes
bash: fork: retry: No child processes
bash: fork: Resource temporarily unavailable
bash-4.2# 
```


### Networking
(10.0.0.1 is the IP address of the container's host)

```
bash-4.2# ping 8.8.8.8 -c 1
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=113 time=27.0 ms

--- 8.8.8.8 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 27.026/27.026/27.026/0.000 ms
bash-4.2# ping 10.0.0.1 -c 1
PING 10.0.0.1 (10.0.0.1) 56(84) bytes of data.
64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=0.033 ms

--- 10.0.0.1 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 0.033/0.033/0.033/0.000 ms
```

[From another terminal]

### Ps and Container Networking
```
$ python3 pocky.py ps
Container Id                             Image                          Cmd                           
eaaa7b2d-cb47-411b-a21d-92468d6077d0     centos:7                       /bin/bash 

$ ping 10.0.0.13 -c 1
PING 10.0.0.13 (10.0.0.13) 56(84) bytes of data.
64 bytes from 10.0.0.13: icmp_seq=1 ttl=64 time=0.091 ms

--- 10.0.0.13 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 0.091/0.091/0.091/0.000 ms
```


## Known Issues / TODO

* Using only chroot for file-system isolation can be bypassed: use pivot_root as well
* Proper handling around startin
* Port forwarding
* Data volumes

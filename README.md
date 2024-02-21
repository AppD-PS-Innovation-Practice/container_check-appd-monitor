container_check-appd-monitor
==============================
A Python script to provide availability status of Docker containers by sending metrics to the standalone Java Machine Agent HTTP Listener.

## Metrics Provided ##
```
|------------------------------+-------------------------------------------------------------------------|
| Name                         + Meaning                                                                 |
|------------------------------+-------------------------------------------------------------------------|
| Status            	       | Overall Status of docker ps --filter status=running                     |
|                   	       | Value:0 - Successful.                                                   |
|                   	       | List of running containers will be 0 or more.                           |
|                   	       | Value:1 - Failure.                                                      |
|                              | Docker is either not running or insufficient permissions to run command.|
|------------------------------+-------------------------------------------------------------------------|
| Availability                 | Up/Down status of the monitored container.                              |
| for each monitored container | Value will be 0 if Up, 1 for Down, or 2 for Unknown.                    |
|                              | Unknown is set when docker ps fails.                                    |
|------------------------------+-------------------------------------------------------------------------|
```

## Prerequisites ##

1. Create user with valid permissions to run docker ps --filter status=running
2. Install machine agent with Machine Agent HTTP Listener enabled
3. Open firewall ports to allow communication from script to HTTP Listener
4. Python 3.9 or later. 3.9 is installed by default on Red Hat Enterprise Linux 9
5. Requests Library 2.31.0 or later - https://requests.readthedocs.io/en/latest/

## Configuration ##

1. Create configuration file with list of containers to monitor. One name per line with no header.
2. Copy Python script to location owned by desired user
3. Update script defaults with above details or supply via command line arguments
4. Create crontab entry to run script at least once every 5 minutes

## High Level Script Overview ##

1. Capture output of docker ps --filter status=running
2. Read monitored_containers.txt
3. Set Status to 1 if either command or fileread operations fail.
4. Set Availability for each monitored container
5. POST Status and Availability metrics to Machine Agent HTTP Listener
6. If POST fails, terminal error occurs which needs to be handled by cron job.

## Python script parameters ##

```
|-------------------------------------------------------------------------------------|
| Name and default values                                                             |
|-------------------------------------------------------------------------------------|
| 'loglevel'                                                                          |
|   help='Logging level - mainly for debugging'                                       |
|   default='ERROR'                                                                   |
|   choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']                         |
|-------------------------------------------------------------------------------------|
| 'sudo_nopasswd'                                                                     |
|   help='Is sudo NOPASSWD required'                                                  |
|   default=True                                                                      |
|   choices=['True', 'False']                                                         |
|-------------------------------------------------------------------------------------|
| 'docker_path'                                                                       |
|   help='Fully qualified path for docker'                                            |
|   default='/usr/bin/docker'                                                         |
|-------------------------------------------------------------------------------------|
| 'timeout'                                                                           |
|   help='subprocess timeout - Must be less than crontab schedule'                    |
|   type=int, default=30                                                              |
|-------------------------------------------------------------------------------------|
| 'monitored_containers_filename'                                                     |
|   help='Config file of list of containers to check with docker ps'                  |
|   default='/appd/extensions/monitored_containers.txt'                               |
|-------------------------------------------------------------------------------------|
| 'machineagent_hostname'                                                             |
|   help='Hostname for machine agent listener'                                        |
|   default='127.0.0.1'                                                               |
|-------------------------------------------------------------------------------------|
| 'machineagent_port'                                                                 |
|   help='Port for machine agent listener'                                            |
|   default=8293                                                                      |
|-------------------------------------------------------------------------------------|
| 'metric_prefix'                                                                     |
|   help='Metric Browser prefix that will appear under machineagent listed above'     |
|   default='Custom Metrics|ContainerCheck'                                           |
|-------------------------------------------------------------------------------------|
```



## Contributing ##

Always feel free to fork and contribute any changes directly via [GitHub][].

## Community ##

Find out more in the [Community][].

## Support ##

For any questions or feature request, please contact [AppDynamics Center of Excellence][].

**Version:** 2.0
**Controller Compatibility:** 3.7 or later
**Memcached Version Tested On:** 1.4.13

[GitHub]: https://github.com/AppD-PS-Innovation-Practice/container_check-appd-monitor
[Community]: http://community.appdynamics.com/
[AppDynamics Center of Excellence]: mailto:ace-request@appdynamics.com



import argparse
import json
import logging
import requests
import subprocess
import sys

def main(loglevel, sudo_nopasswd, docker_path, timeout, monitored_containers_filename, machineagent_hostname,
         machineagent_port, metric_prefix):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s\n", level=loglevel)
    metrics_url = f'http://{machineagent_hostname}:{machineagent_port}/api/v1/metrics'
    headers = {'Content-Type': 'application/json'}
    """
    status is for docker ps overall status
    unknown is used for container Availability state in case docker ps fails
    Only change if docker ps works
    There will always be a POST for Status even if there are issues
    """
    status = 1
    unknown = 1
    post_metrics = []
    # Convert True/False string to boolean
    sudo_nopasswd = eval(f'{sudo_nopasswd}')
    logging.info(f'sudo flag: {sudo_nopasswd}')
    try:
        if sudo_nopasswd:
            docker_command = ['sudo', docker_path,
                              'ps', '--filter', 'status=running']
        else:
            docker_command = [docker_path, 'ps', '--filter', 'status=running']
        logging.info(f'docker ps command: {docker_command}')
        run_docker_ps = subprocess.run(
            docker_command, timeout=timeout, check=True, capture_output=True, text=True)
        logging.info(f'docker ps output:\n{run_docker_ps}')
        unknown = 0
        stdout_running_containers = run_docker_ps.stdout.splitlines()
        running_containers_list = stdout_running_containers[1::]
        running_containers = []
        for container in running_containers_list:
            name_only = container.split()[-1]
            running_containers.append(name_only)
        running_containers = sorted(running_containers)
        try:
            with open(monitored_containers_filename, "r") as monitored_containers_file:
                monitored_containers = monitored_containers_file.read().splitlines()
            # Change status since both docker ps and monitored_containers_file.read successful
            status = 0
            monitored_containers = sorted(monitored_containers)
            logging.info(f'monitored_containers:\n{monitored_containers}')
            logging.info(f'Running names:\n{running_containers}')
            logging.info(f'status flag is {status}')
            logging.info(f'unknown flag is {unknown}')
            for monitored_container in monitored_containers:
                availability = 1
                metric_name = f'{metric_prefix}|{monitored_container}|Availability'
                if unknown:
                    availability = 2
                elif monitored_container in running_containers:
                    availability = 0
                    logging.info(
                        f'{monitored_container} is running. Availability:{availability}')
                else:
                    availability = 1
                    logging.info(
                        f'{monitored_container} is NOT running. Availability:{availability}')
                payload = json.dumps([
                    {
                        "metricName": metric_name,
                        "aggregatorType": "OBSERVATION",
                        "value": availability
                    }
                ])
                logging.info(payload)
                post_metrics.append(payload)
        except:
            logging.error('Unable to open {monitored_containers_filename}')
    except FileNotFoundError as exc:
        logging.error(f'docker executable could not be found.\n{exc}')
        # print(f'docker executable could not be found.\n{exc}')
    except subprocess.CalledProcessError as exc:
        logging.error(f'docker ps error - most likely permissions issue.')
        logging.error(f'Returned {exc.returncode}\n{exc}')
    except OSError as exc:
        logging.error(f'OS Error Exception.\n{exc}')
    except ValueError as exc:
        logging.error(f'Invalid Arguments.\n{exc}')
    except subprocess.TimeoutExpired as exc:
        logging.error('TimedOut')
    finally:
        metric_name = f'{metric_prefix}|Status'
        payload = json.dumps([
            {
                "metricName": metric_name,
                "aggregatorType": "OBSERVATION",
                "value": status
            }])
        logging.info(payload)
        post_metrics.insert(0, payload)
        with requests.Session() as session:
            session.headers = headers
            # Iterate over payload list
            for data in post_metrics:
                try:
                    response = session.post(metrics_url, data=data)
                    logging.info(f'JSON Payload is {data}')
                    logging.info(
                        f'POST Status Code: {response.status_code} POST Response: {response.text}')
                    # Status code will be 204 as listener responds with no_content
                    if response.status_code != 204:
                        logging.error(
                            f'Expected 204. Got {response.status_code} for status code')
                except requests.exceptions.RequestException as exc:
                    logging.error(
                        f'POST failed for {metrics_url} with payload {data}\n{exc}')
                    sys.exit(1)


"""
Review permissions with your security team to run docker commands
docker ps --filter status=running
/usr/bin/docker ps --filter status=running

If docker running as root which is default then sudo is required
https://docs.docker.com/engine/install/linux-postinstall/
https://docs.docker.com/engine/security/#docker-daemon-attack-surface

One option is to place this command in /etc/sudoers.d/USERNAME
USERNAME HOSTNAME= NOPASSWD: /usr/bin/docker ps --filter status=running
"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('loglevel', help='Logging level - mainly for debugging',
                        nargs='?', default='ERROR', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument('sudo_nopasswd', help='Is sudo NOPASSWD required',
                        nargs='?', default=True, choices=['True', 'False'])
    parser.add_argument('docker_path', help='Fully qualified path for docker',
                        nargs='?', default='/usr/bin/docker')
    parser.add_argument('timeout', help='subprocess timeout - Must be less than crontab schedule',
                        nargs='?', type=int, default=30)
    parser.add_argument("monitored_containers_filename", help='Config file of list of containers to check with docker ps',
                        nargs='?', default='/appd/extensions/monitored_containers.txt')
    parser.add_argument('machineagent_hostname',
                        help='Hostname for machine agent listener', nargs='?', default='127.0.0.1')
    parser.add_argument(
        'machineagent_port', help='Port for machine agent listener', nargs='?',  default=8293)
    parser.add_argument('metric_prefix', help='Metric Browser prefix that will appear under machineagent listed above',
                        nargs='?', default='Custom Metrics|DOCKER_PS')
    args = parser.parse_args()
    # print(args)
    main(args.loglevel, args.sudo_nopasswd, args.docker_path, args.timeout, args.monitored_containers_filename, args.machineagent_hostname,
         args.machineagent_port, args.metric_prefix)

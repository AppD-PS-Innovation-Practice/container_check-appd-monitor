# Script requires Requests Library 2.31.0 or later - https://requests.readthedocs.io/en/latest/
import argparse
import json
import logging
import requests
import subprocess
import sys


def main(metrictype, loglevel, sudo_nopasswd, docker_path, timeout,
         monitored_containers_filename, machineagent_hostname,
         machineagent_port, metric_prefix,
         custom_schema, appd_acctname, appd_apikey):
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s\n", level=loglevel)
    metrics_url = f'http://{machineagent_hostname}:{machineagent_port}/api/v1/metrics'
    ma_headers = {'Content-Type': 'application/json'}
    analytics_url = f'https://analytics.api.appdynamics.com/events/publish/{custom_schema}'
    analytics_headers = {'X-Events-API-AccountName': appd_acctname,
                         'X-Events-API-Key': appd_apikey,
                         'Content-Type': 'application/vnd.appd.events+json;v=2',
                         'Accept': 'application/vnd.appd.events+json;v=2'}

    """
    status is for docker stats overall status
    unknown is used for container Availability state in case docker stats fails
    Only change if docker stats works
    There will always be a POST for Status even if there are issues
    """
    status = 1
    unknown = 1
    ma_custom_metrics = []
    analytics_custom_schema = []
    running_containers = []
    # Convert True/False string to boolean
    sudo_nopasswd = eval(f'{sudo_nopasswd}')
    logging.info(f'sudo flag: {sudo_nopasswd}')
    try:
        if sudo_nopasswd:
            docker_command = ['sudo', docker_path,
                              'stats', '--no-stream']
        else:
            docker_command = [docker_path, 'stats', '--no-stream']
        logging.info(f'docker stats command: {docker_command}')
        run_docker_stats = subprocess.run(
            docker_command, timeout=timeout, check=True, capture_output=True, text=True)
        logging.info(f'docker stats output:\n{run_docker_stats}')
        unknown = 0
        stdout_running_containers = run_docker_stats.stdout.splitlines()
        running_containers_list = stdout_running_containers[1::]
        for container in running_containers_list:
            container_name = container.split()[1]
            container_cpu = container.split()[2]
            container_memory = container.split()[6]
            container_entry = [container_name, container_cpu, container_memory]
            logging.info(f'container_entry:\n{container_entry}')
            running_containers.append(container_entry)
            running_containers = sorted(running_containers)
    except FileNotFoundError as exc:
        logging.error(f'docker executable could not be found.\n{exc}')
        # print(f'docker executable could not be found.\n{exc}')
    except subprocess.CalledProcessError as exc:
        logging.error(f'docker stats error - most likely permissions issue.')
        logging.error(f'Returned {exc.returncode}\n{exc}')
    except OSError as exc:
        logging.error(f'OS Error Exception.\n{exc}')
    except ValueError as exc:
        logging.error(f'Invalid Arguments.\n{exc}')
    except subprocess.TimeoutExpired as exc:
        logging.error(
            'subprocess command TimeoutExpired. Most likely when waiting for interactive password reply.')
    finally:
        try:
            with open(monitored_containers_filename, "r") as monitored_containers_file:
                monitored_containers = monitored_containers_file.read().splitlines()
            # Change status since both docker stats and monitored_containers_file.read successful
            if not unknown:
                status = 0
            monitored_containers = sorted(monitored_containers)
            logging.info(f'monitored_containers:\n{monitored_containers}')
            logging.info(f'running_containers:\n{running_containers}')
            logging.info(f'status flag is {status}')
            logging.info(f'unknown flag is {unknown}')
            for monitored_container in monitored_containers:
                availability = 1
                cpu = -1
                memory = -1
                metric_availability = f'{metric_prefix}|Availability|{monitored_container}'
                metric_cpu = f'{metric_prefix}|{monitored_container}|CPU'
                metric_memory = f'{metric_prefix}|{monitored_container}|Memory'
                if unknown:
                    availability = 2
                    cpu = 999
                    memory = 999
                else:
                    for rc in running_containers:
                        availability = 1
                        cpu = 999
                        memory = 999
                        rc_name = rc[0]
                        rc_name = rc_name.replace('%', '')
                        rc_cpu = rc[1]
                        rc_cpu = rc_cpu.replace('%', '')
                        rc_cpu = float(rc_cpu)
                        rc_memory = rc[2]
                        rc_memory = rc_memory.replace('%', '')
                        rc_memory = float(rc_memory)
                        logging.info(f'rc_name is {rc_name}, rc_cpu is {rc_cpu}, rc_memory is {rc_memory}')

                        if monitored_container == rc_name:
                            availability = 0
                            logging.info(f'{monitored_container} is running. Availability:{availability}')
                            cpu = rc_cpu
                            memory = rc_memory
                            break

                    if availability == 1:

                        if metrictype=='MachineAgent' or metrictype=='MachineAgent+Analytics':

                            logging.info(f'{monitored_container} is NOT running. Availability:{availability}')
                            ma_payload = json.dumps([
                                {
                                    "metricName": metric_availability,
                                    "aggregatorType": "OBSERVATION",
                                    "value": availability
                                }
                                ])
                        if metrictype=='Analytics' or metrictype=='MachineAgent+Analytics':
                            analytics_payload = json.dumps([
                                {
                                    "name": rc_name,
                                    "availability": availability,
                                }
                                ])
                    else:

                        if metrictype=='MachineAgent' or metrictype=='MachineAgent+Analytics':
                            ma_payload = json.dumps([
                                {
                                    "metricName": metric_availability,
                                    "aggregatorType": "OBSERVATION",
                                    "value": availability
                                },
                                {
                                    "metricName": metric_cpu,
                                    "aggregatorType": "OBSERVATION",
                                    "value": cpu
                                },
                                {
                                    "metricName": metric_memory,
                                    "aggregatorType": "OBSERVATION",
                                    "value": memory
                                }
                                ])

                            logging.info(f'going to add post ma_payload metrics: {ma_payload}')
                            ma_custom_metrics.append(ma_payload)

                        if metrictype=='Analytics' or metrictype=='MachineAgent+Analytics':
                            analytics_payload = json.dumps([
                                {
                                    "name": rc_name,
                                    "availability": availability,
                                    "cpu": cpu,
                                    "memory": memory
                                }
                                ])

                            logging.info(f'going to add post analytics_payload metrics: {analytics_payload}')
                            analytics_custom_schema.append(analytics_payload)

        except Exception as error:
            logging.error(f'An exception occurred: {error}')
            # logging.error(f'Unable to open {monitored_containers_filename}')

        if metrictype=='MachineAgent' or metrictype=='MachineAgent+Analytics':
            metric_name = f'{metric_prefix}|Status'
            ma_payload = json.dumps([
                {
                    "metricName": metric_name,
                    "aggregatorType": "OBSERVATION",
                    "value": status
                }])
            logging.info(f'ma_payload is {ma_payload}')
            ma_custom_metrics.insert(0, ma_payload)

        with requests.Session() as session:
            session.headers = ma_headers
            # Iterate over ma_payload list
            for data in ma_custom_metrics:
                try:
                    logging.info(f'session.headers is {session.headers}')
                    logging.info(f'metrics_url is {metrics_url}')
                    logging.info(f'JSON MA Payload is {data}')
                    response = session.post(metrics_url, data=data)
                    logging.info(
                        f'POST Status Code: {response.status_code} POST Response: {response.text}')
                    # Status code will be 204 as listener responds with no_content
                    if response.status_code != 204:
                        logging.error(
                            f'Expected 204. Got {response.status_code} for status code')
                except requests.exceptions.RequestException as exc:
                    logging.error(
                        f'POST failed for {metrics_url} with ma_payload {data}\n{exc}')
                    sys.exit(1)

            session.headers = analytics_headers
            for data in analytics_custom_schema:
                try:
                    logging.info(f'session.headers is {session.headers}')
                    logging.info(f'analytics_url is {analytics_url}')
                    logging.info(f'JSON Analytics Payload is {data}')
                    response = session.post(analytics_url, data=data)
                    logging.info(
                        f'POST Status Code: {response.status_code} POST Response: {response.text}')
                    # Status code will be 204 as listener responds with no_content
                    if response.status_code != 204:
                        logging.error(
                            f'Expected 204. Got {response.status_code} for status code')
                except requests.exceptions.RequestException as exc:
                    logging.error(
                        f'POST failed for {analytics_url} with analytics_payload {data}\n{exc}')
                    sys.exit(1)


"""
Review permissions with your security team to run docker commands
docker stats --no-stream
/usr/bin/docker stats --no-stream

If docker running as root which is default then sudo is required
https://docs.docker.com/engine/install/linux-postinstall/
https://docs.docker.com/engine/security/#docker-daemon-attack-surface

One option is to place this command in /etc/sudoers.d/USERNAME
USERNAME HOSTNAME= NOPASSWD: /usr/bin/docker stats --filter --no-stream
"""

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('metrictype',
                        help='machine agent or analytics custom schema',
                        nargs='?',
                        default='MachineAgent', choices=['MachineAgent', 'Analytics', 'MachineAgent+Analytics'])
    parser.add_argument('loglevel',
                        help='Logging level - mainly for debugging',
                        nargs='?',
                        default='ERROR', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
    parser.add_argument('sudo_nopasswd',
                        help='Is sudo NOPASSWD required',
                        nargs='?',
                        default=True, choices=['True', 'False'])
    parser.add_argument('docker_path',
                        help='Fully qualified path for docker',
                        nargs='?',
                        default='/usr/bin/docker')
    parser.add_argument('timeout',
                        help='subprocess timeout - Must be less than crontab schedule',
                        nargs='?',
                        type=int, default=30)
    parser.add_argument('monitored_containers_filename',
                        help='Config file of list of containers to check with docker stats',
                        nargs='?',
                        default='/appd/extensions/monitored_containers.txt')
    parser.add_argument('machineagent_hostname',
                        help='Hostname for machine agent listener',
                        nargs='?', default='127.0.0.1')
    parser.add_argument('machineagent_port',
                        help='Port for machine agent listener',
                        nargs='?',  default=8293)
    parser.add_argument('metric_prefix',
                        help='Metric Browser prefix that will appear under machineagent listed above',
                        nargs='?',
                        default='Custom Metrics|ContainerCheck')
    parser.add_argument('custom_schema',
                        help='custom_schema',
                        nargs='?', default='custom_schema')
    parser.add_argument('appd_acctname',
                        help='appd_acctname',
                        nargs='?', default='appd_acctname')
    parser.add_argument('appd_apikey',
                        help='appd_apikey',
                        nargs='?', default='appd_apikey')
    args = parser.parse_args()
    # print(args)
    main(args.metrictype, args.loglevel, args.sudo_nopasswd, args.docker_path, args.timeout,
         args.monitored_containers_filename, args.machineagent_hostname,
         args.machineagent_port, args.metric_prefix,
         args.custom_schema, args.appd_acctname, args.appd_apikey)

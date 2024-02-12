import argparse
import json
import requests
import subprocess

def main(monitored_containers_filename, machineagent_hostname, machineagent_port, timeout, docker_path, metric_prefix):
    metrics_url = f'http://{machineagent_hostname}:{machineagent_port}/api/v1/metrics'
    headers = {'Content-Type': 'application/json'}
    """
    status is for docker ps overall status
    unknown is used for container Availability state in case docker ps fails
    Only change if docker ps works
    """
    status = 1
    unknown = 1

    try:
        run_docker_ps = subprocess.run(
            [docker_path, 'ps'], timeout=timeout, check=True, capture_output=True, text=True)
        status = 0
        unknown = 0
        stdout_running_containers = run_docker_ps.stdout.splitlines()
        running_containers_list = stdout_running_containers[1::]
        running_containers = []
        for container in running_containers_list:
            name_only = container.split()[-1]
            running_containers.append(name_only)
        running_containers = sorted(running_containers)
    except FileNotFoundError as exc:
        print(f'docker executable could not be found.\n{exc}')
    except subprocess.CalledProcessError as exc:
        print('docker ps error - most likely permissions issue.')
        print(f'Returned {exc.returncode}\n{exc}')
    except OSError as exc:
        print(f'OS Error Exception.\n{exc}')
    except ValueError as exc:
        print(f'Invalid Arguments.\n{exc}')
    except subprocess.TimeoutExpired as exc:
        print('TimedOut')

    with open(monitored_containers_filename, "r") as monitored_containers_file:
        monitored_containers = monitored_containers_file.read().splitlines()
        monitored_containers = sorted(monitored_containers)

    # print(f'monitored_containers:\n{monitored_containers}')
    # print(f'Running names:\n{running_containers}')
    # print(f'status flag is {status}')
    # print(f'unknown flag is {unknown}')
    # Initialize list for metrics to be posted
    post_metrics = []
    with requests.Session() as session:
        session.headers = headers
        # Iterate over running and reset availability each time to mark as unavailable
        for monitored_container in monitored_containers:
            availability = 1
            metric_name = f'{metric_prefix}|{monitored_container}|Availability'
            if unknown:
                availability = 2
            elif monitored_container in running_containers:  # Monitored in running
                availability = 0
                # print(f'{monitored_container} is running.\navailability:{availability}\n')
            else:
                availability = 1
                # print(f'{monitored_container} is NOT running.\navailability:{availability}\n')
            payload = json.dumps([
                {
                    "metricName": metric_name,
                    "aggregatorType": "OBSERVATION",
                    "value": availability
                }
            ])
            #print(payload)
            response = session.post(metrics_url, data=payload)
            # Status code will be 204 as listener responds with no_content
            if response.status_code != 204:
                print(response.status_code)
                print(response.text)

        # Container Availability processing now complete so POST overall status
        metric_name = f'{metric_prefix}|Status'
        payload = json.dumps([
            {
                "metricName": metric_name,
                "aggregatorType": "OBSERVATION",
                "value": status
            }])
        #print(payload)
        response = session.post(metrics_url, data=payload)
        # Status code will be 204 as listener responds with no_content
        if response.status_code != 204:
            print(response.status_code)
            print(response.text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("monitored_containers_filename", help='Config file of list of containers to check with docker ps',
                        nargs='?', default='/appd/extensions/monitored_containers.txt')
    parser.add_argument('machineagent_hostname',
                        help='Hostname for machine agent listener', nargs='?', default='127.0.0.1')
    parser.add_argument(
        'machineagent_port', help='Port for machine agent listener', nargs='?',  default=8293)
    parser.add_argument('timeout', help='subprocess timeout',
                        nargs='?', default=10)
    parser.add_argument('docker_path', help='Fully qualifies path for docker',
                        nargs='?', default='/usr/bin/docker')
    parser.add_argument('metric_prefix', help='Fully qualifies path for docker',
                        nargs='?', default='Custom Metrics|DOCKER_PS')
    args = parser.parse_args()
    # print(args)
    main(args.monitored_containers_filename, args.machineagent_hostname,
         args.machineagent_port, args.timeout, args.docker_path, args.metric_prefix)

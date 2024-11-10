from typing import List
import requests
import argparse
import json


def read_secrets(file_path="secrets.json"):
    try:
        with open(file_path, "r") as secrets_file:
            secrets_data = json.load(secrets_file)
            return secrets_data.get("access_token"), secrets_data.get('portainer_api_url')
    except FileNotFoundError:
        print(f"Secrets file not found: {file_path}")
    except json.JSONDecodeError:
        print("Error parsing JSON in secrets file.")
    return None, None


access_token, portainer_api_url = read_secrets()


def get_endpoint_id(endpoint_name='Quasar'):
    headers = {
        "X-API-Key": f"{access_token}",
    }
    endpoint_id = None
    # Get a list of all endpoints
    endpoints_response = requests.get(f"{portainer_api_url}/endpoints", headers=headers)
    endpoints = endpoints_response.json()

    if "message" in endpoints:
        print(f"failed to get endpoint list: {endpoints['message']}")
        return

    found_endpoint = None
    for endpoint in endpoints:
        if endpoint["Name"] == endpoint_name:
            found_endpoint = endpoint
            break

    if found_endpoint:
        endpoint_id = found_endpoint["Id"]
        print(f"endpoint ID for '{endpoint_name}': {endpoint_id}")
    else:
        print(f"endpoint with the name '{endpoint_name}' not found.")
    return endpoint_id


def get_running_stacks(endpoint_id='Quasar'):
    headers = {
        "X-API-Key": f"{access_token}",
    }
    query_params = {
        "endpointId": endpoint_id,
    }
    # Get a list of all stacks
    stacks_response = requests.get(f"{portainer_api_url}/stacks", headers=headers, params=query_params)
    stacks = stacks_response.json()

    if "message" in stacks:
        print(f"failed to get stack list: {stacks['message']}")
        return

    running_stacks = []
    for stack in stacks:
        if stack["Status"] == 1:
            running_stacks.append(stack)
    return running_stacks


def command_single(stack_name: str, start=True):
    headers = {
        "X-API-Key": f"{access_token}",
    }

    command = "start" if start else "stop"
    endpoint_id = get_endpoint_id()
    query_params = {
        "endpointId": endpoint_id,
    }

    stacks = requests.get(f"{portainer_api_url}/stacks", headers=headers, params=query_params).json()

    found_stack = None
    for stack in stacks:
        if stack["Name"] == stack_name:
            found_stack = stack
            break
    if not found_stack:
        print(f"stack with the name '{stack_name}' not found.")
        return

    stack_id = found_stack["Id"]
    stack_name = found_stack["Name"]
    print(f"{'starting' if start else 'stopping'} stack: {stack_name} (ID: {stack_id})")

    response = requests.post(f"{portainer_api_url}/stacks/{stack_id}/{command}",
                                  headers=headers, params=query_params)

    if response.status_code == 200:
        print(f"stack {stack_name} {'started' if start else 'stopped'} successfully.")
    else:
        print(f"failed to {'start' if start else 'stop'} stack {stack_name}. status code: {response.status_code}")


def command_all(start=True, stack_id_list: List[dict] = None):
    headers = {
        "X-API-Key": f"{access_token}",
    }

    command = "start" if start else "stop"

    endpoint_id = get_endpoint_id()
    query_params = {
        "endpointId": endpoint_id,
    }
    # Get a list of all stacks
    stacks_response = requests.get(f"{portainer_api_url}/stacks", headers=headers, params=query_params)
    stacks = stacks_response.json()

    if "message" in stacks:
        print(f"failed to get stack list: {stacks['message']}")
        return


    if stack_id_list:
        for stack in stack_id_list:
            stack_id = stack["Id"]
            stack_name = stack["Name"]
            print(f"{'starting' if start else 'stopping'} stack: {stack_name} (ID: {stack_id})")
            stop_response = requests.post(f"{portainer_api_url}/stacks/{stack_id}/{command}",
                                        headers=headers, params=query_params)
            if stop_response.status_code == 200:
                print(f"stack {stack_name} {'started' if start else 'stopped'} successfully.")
            else:
                print(
                    f"failed to {'start' if start else 'stop'} stack {stack_name}. status code: {stop_response.status_code}")

    else:
        # Iterate through all stacks and stop them
        for stack in stacks:
            stack_id = stack["Id"]
            stack_name = stack["Name"]
            print(f"{'starting' if start else 'stopping'} stack: {stack_name} (ID: {stack_id})")
            stop_response = requests.post(f"{portainer_api_url}/stacks/{stack_id}/{command}",
                                        headers=headers, params=query_params)
            if stop_response.status_code == 200:
                print(f"stack {stack_name} {'started' if start else 'stopped'} successfully.")
            else:
                print(
                    f"failed to {'start' if start else 'stop'} stack {stack_name}. status code: {stop_response.status_code}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stop Portainer stacks.")
    parser.add_argument("--stack-name", help="Name of the specific stack to stop")
    parser.add_argument("--all", action="store_true", help="Stop all running stacks")
    parser.add_argument("--stop", action="store_true", help="Stop stacks")
    parser.add_argument("--start", action="store_true", help="Start stacks")
    parser.add_argument("--restart", action="store_true", help="Restart stacks")

    args = parser.parse_args()

    if args.all and args.stack_name:
        print("you can't specify both '--all' and '--stack-name' options.")
    elif args.all:
        if args.restart:
            stacks = get_running_stacks()
            command_all(start=False, stack_id_list=stacks)
            command_all(start=True, stack_id_list=stacks)
        elif args.start:
            command_all(start=True)
        elif args.stop:
            command_all(start=False)
    elif args.stack_name:
        if args.restart:
            command_single(stack_name=args.stack_name, start=False)
            command_single(stack_name=args.stack_name, start=True)
        elif args.start:
            command_single(stack_name=args.stack_name, start=True)
        elif args.stop:
            command_single(stack_name=args.stack_name, start=False)
    else:
        print("please specify either '--all' to stop all stacks or '--stack-name' to stop a specific stack.")

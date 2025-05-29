import requests
from requests.auth import HTTPBasicAuth
from prefect.blocks.system import Secret


env_block = Secret.load("spheredefaultenv")
env_data = env_block.get()


def send_notification_to_ntfy(ntfy_topic: str, message: str):
    ntfy_url = env_data["NTFY_URL"]
    ntfy_auth = HTTPBasicAuth(env_data["HTTPBASICAUTH_USER"], env_data["HTTPBASICAUTH_PASSWORD"])

    try:
        response = requests.post(
            f"{ntfy_url}/{ntfy_topic}",
            data=message,
            auth=ntfy_auth
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to send notification: {e}")
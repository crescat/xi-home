import requests
import json
from requests.adapters import HTTPAdapter, Retry
from .const import TIMEOUT, RETRY, API_PREFIX


def header(token: str) -> dict[str, str]:
    """
    Returns a dictionary containing the authorization and content-type headers
    for a request to the API.

    Args:
        token (str): The authorization token to include in the request header.

    Returns:
        dict[str, str]: A dictionary containing the authorization and content-type headers.
    """
    return {
        "authorization": "Bearer {}".format(token),
        "content-type": "application/json",
    }


def request_data(path, token, params):
    """
    Sends a POST request to the API with the given path, token, and parameters.

    Args:
        path (str): The path to send the request to.
        token (str): The authorization token to include in the request header.
        params (dict): The parameters to include in the request body.

    Returns:
        dict: The JSON response from the API.
    """
    data = json.dumps(params)
    url = API_PREFIX + path
    s = requests.Session()
    retries = Retry(
        total=RETRY,
        # 0s, 10s, 20s, 40s, 80s...
        backoff_factor=5,
        status_forcelist=[500, 502, 503, 504],
        # allow retry on POST requests
        allowed_methods=None,
    )

    s.mount(API_PREFIX, HTTPAdapter(max_retries=retries))
    response = s.post(url, data=data, headers=header(token), timeout=TIMEOUT)

    return response.json()

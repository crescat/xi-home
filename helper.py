import requests
import json
from requests.adapters import HTTPAdapter, Retry
from .const import TIMEOUT, RETRY, API_PREFIX

def header(token: str) -> dict[str, str]:
    return {
            "authorization": "Bearer {}".format(token),
            "content-type": "application/json",
        }

def request_data(path, token, params):
    data = json.dumps(params)
    url = API_PREFIX + path
    # RetryAdapter 3 times
    s = requests.Session()
    retries = Retry(total=RETRY,
                backoff_factor=0.1,
                status_forcelist=[ 500, 502, 503, 504 ])
    s.mount(API_PREFIX, HTTPAdapter(max_retries=retries))
    response = s.post(url, data=data, headers=header(token), timeout=TIMEOUT)
    return response.json()



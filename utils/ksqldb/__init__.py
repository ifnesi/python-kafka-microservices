import sys
import requests

from urllib.parse import urlencode
from requests.auth import HTTPBasicAuth

from utils import log_exception


class KsqlDB:
    def __init__(
        self,
        end_point: str = "http://localhost:8088",
        username: str = None,
        password: str = None,
    ):
        self.end_point = end_point.strip("/")
        # Authorization
        if None not in (username, password):
            self.auth = HTTPBasicAuth(username, password)
        else:
            self.auth = None

    def _request(
        self,
        method: str = "POST",
        path: str = "",
        query: dict = None,
        json: dict = None,
        headers: dict = None,
    ) -> tuple:
        """Submit POST request to ksqlDB Server"""

        if not isinstance(headers, dict):
            headers = dict()

        # Default heders
        headers_request = {
            "Content-Type": "application/json",
            "Accept": "application/vnd.ksql.v1+json",
        }
        # Update headers if needed
        headers_request.update(headers)

        # Set query parameters if needed
        if isinstance(query, dict):
            query_string = f"?{urlencode(query)}"
        else:
            query_string = ""

        # Set URL
        url = f"""{self.end_point}/{path.lstrip("/")}{query_string}"""

        try:
            # Submit request
            if method == "GET":
                r = requests.get(
                    url,
                    auth=self.auth,
                    headers=headers_request,
                )
            else:  # Default POST
                r = requests.post(
                    url,
                    auth=self.auth,
                    headers=headers_request,
                    json=json,
                )

            # Response
            response = r.json()
            status_code = r.status_code

        except requests.exceptions.Timeout:
            response = None
            status_code = 408

        except Exception:
            response = None
            try:
                status_code = r.status_code
            except Exception:
                status_code = 502
            log_exception(
                f"Unable to send {method} request ({status_code}): {url}",
                sys.exc_info(),
            )

        finally:
            return status_code, response

    def query(self, query: dict) -> tuple:
        return self._request(
            path="ksql",
            json=query,
        )

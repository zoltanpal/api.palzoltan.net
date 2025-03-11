from fastapi import HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.requests import Request

from config import WEBUI_USER
from libs.responses import responses



class BasicAuth(HTTPBasic):

    def __init__(self, auto_error: bool = True):
        super(BasicAuth, self).__init__(auto_error=auto_error)
        try:
            self.credentials = {WEBUI_USER[0]: WEBUI_USER[1]}
        except KeyError:
            self.credentials = {"testuser":"testuserpw"}

    async def __call__(self, request: Request):
        credentials: HTTPBasicCredentials = await super(
            BasicAuth, self
        ).__call__(request)
        if credentials:
            if credentials.username not in self.credentials \
                    or credentials.password != self.credentials[credentials.username]:
                raise HTTPException(status_code=403, detail=responses[403]["message"])
        else:
            raise HTTPException(status_code=401, detail="Invalid authorization code.")

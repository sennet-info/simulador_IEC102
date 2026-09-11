from __future__ import annotations

from dataclasses import dataclass

from .constants import (
    MASTER_REQUEST_CLASS_2_DATA,
    MASTER_REQUEST_LINK_STATUS,
    MASTER_RESET_REMOTE_LINK,
    MASTER_SEND_USER_DATA,
    SLAVE_ACK,
    SLAVE_NACK,
    SLAVE_NO_DATA,
    SLAVE_STATUS,
    SLAVE_USER_DATA,
)
from .encoder import encode_fixed_frame, encode_variable_frame
from .frame import LinkFrame


@dataclass(slots=True)
class LinkResponse:
    raw: bytes
    description: str


class LinkLayer:
    def ack(self, address: int, description: str = "ACK") -> LinkResponse:
        return LinkResponse(encode_fixed_frame(SLAVE_ACK, address), description)

    def nack(self, address: int, description: str = "NACK") -> LinkResponse:
        return LinkResponse(encode_fixed_frame(SLAVE_NACK, address), description)

    def no_data(self, address: int, description: str = "NO DATA") -> LinkResponse:
        return LinkResponse(encode_fixed_frame(SLAVE_NO_DATA, address), description)

    def status(self, address: int, description: str = "STATUS") -> LinkResponse:
        return LinkResponse(encode_fixed_frame(SLAVE_STATUS, address), description)

    def user_data(self, address: int, payload: bytes, description: str) -> LinkResponse:
        return LinkResponse(encode_variable_frame(SLAVE_USER_DATA, address, payload), description)

    def respond_to_non_data_request(self, frame: LinkFrame) -> LinkResponse | None:
        if frame.function_code == MASTER_RESET_REMOTE_LINK:
            return self.ack(frame.address, "Link reset acknowledged")
        if frame.function_code == MASTER_REQUEST_LINK_STATUS:
            return self.status(frame.address, "Link status")
        if frame.function_code == MASTER_REQUEST_CLASS_2_DATA:
            return self.no_data(frame.address, "No class 2 data queued")
        if frame.function_code == MASTER_SEND_USER_DATA:
            return None
        return self.nack(frame.address, f"Unsupported function {frame.function_code}")

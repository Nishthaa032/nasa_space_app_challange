"""Strict HTTP range reader for h5py: never silently fetch a whole HDF5 file."""

import io
import re
from contextlib import contextmanager
from urllib.parse import urlparse
from collections import OrderedDict

import httpx

from .catalog import science_url
from .settings import TOKEN, TRANSFER_LIMIT, USER_AGENT


class RangeRequired(ValueError):
    pass


class RangeFile(io.RawIOBase):
    def __init__(self, url, token=TOKEN, budget=TRANSFER_LIMIT, client=None, allow_signed_redirect=False):
        if not science_url(url):
            raise ValueError("Only catalog-verified NASA NISAR HTTPS files are supported.")
        if not token:
            raise ValueError(
                "Set EARTHDATA_TOKEN in the local .env file, then restart the backend."
            )
        self.url = url
        self.allow_signed_redirect = allow_signed_redirect
        self.signed_url = None
        self.position = 0
        self.transferred = 0
        self.budget = budget
        self.blocks = OrderedDict()
        self.block_size = 256 * 1024
        self.client = client or httpx.Client(
            timeout=45, follow_redirects=False, headers={"User-Agent": USER_AGENT}
        )
        self.owns_client = client is None
        self.token = token
        self.size = None
        # Probe one byte. A 200/redirect is rejected before reading its body.
        self._fetch(0, 0)

    @contextmanager
    def _range_response(self, start, end):
        headers = {"Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"}
        if self.signed_url:
            with self.client.stream("GET", self.signed_url, headers=headers, follow_redirects=False) as response:
                yield response
            return
        with self.client.stream("GET", self.url, headers={**headers, "Authorization": f"Bearer {self.token}"}, follow_redirects=False) as response:
            location = response.headers.get("Location", "")
            target = urlparse(location)
            if (self.allow_signed_redirect and response.status_code == 303
                    and target.scheme == "https" and target.hostname == "d1mv8zhcvry6x4.cloudfront.net"
                    and not target.username and not target.password and target.port in (None, 443)):
                self.signed_url = location
            else:
                yield response
                return
        # NASA's signed delivery URL is kept in memory; never forward Earthdata credentials.
        with self.client.stream("GET", self.signed_url, headers=headers, follow_redirects=False) as response:
            yield response

    def _fetch(self, start, end):
        if self.transferred + end - start + 1 > self.budget:
            raise RangeRequired(
                "Selected-area transfer cap reached. No full file was downloaded. Try a smaller area."
            )
        with self._range_response(start, end) as response:
            if response.status_code in [401, 403]:
                raise ValueError(
                    "Earthdata authentication was rejected. Check token validity and NASA data-access authorization."
                )
            if response.status_code != 206:
                raise RangeRequired(
                    "NASA did not provide a partial response. Full-file access requires separate approval; no full download was started."
                )
            match = re.fullmatch(
                r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
            )
            if not match or int(match[1]) != start or int(match[2]) != end:
                raise RangeRequired("Invalid range response; transfer stopped.")
            size = int(match[3])
            if self.size is not None and size != self.size:
                raise RangeRequired("Remote file changed during reading; retry later.")
            self.size = size
            chunks = []
            count = 0
            for chunk in response.iter_bytes():
                count += len(chunk)
                self.transferred += len(chunk)
                if count > end - start + 1 or self.transferred > self.budget:
                    raise RangeRequired("Transfer exceeded the requested range; stopped.")
                chunks.append(chunk)
            if count != end - start + 1:
                raise RangeRequired("Incomplete range response.")
            return b"".join(chunks)

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = (
            offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        )
        if position < 0:
            raise ValueError("Negative seek")
        self.position = position
        return position

    def read(self, size=-1):
        size = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if size <= 0:
            return b""
        out = []
        while size:
            index = self.position // self.block_size
            if index not in self.blocks:
                start = index * self.block_size
                end = min(start + self.block_size, self.size) - 1
                self.blocks[index] = self._fetch(start, end)
                while len(self.blocks) > 32:
                    self.blocks.popitem(last=False)
            self.blocks.move_to_end(index)
            offset = self.position % self.block_size
            part = self.blocks[index][offset : offset + size]
            out.append(part)
            self.position += len(part)
            size -= len(part)
        return b"".join(out)

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def close(self):
        if self.owns_client:
            self.client.close()
        self.blocks.clear()
        super().close()

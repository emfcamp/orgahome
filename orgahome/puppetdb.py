"""Minimal PuppetDB client."""

import abc
import json
import logging
import ssl
import typing
from contextlib import asynccontextmanager

import aiohttp

logger = logging.getLogger(__name__)


class PuppetOSReleaseFact(typing.TypedDict):
    full: str
    major: str
    minor: str


class PuppetDistroFact(typing.TypedDict):
    id: str
    release: PuppetOSReleaseFact
    codename: str
    description: str


class PuppetOSFact(typing.TypedDict):
    name: str
    distro: PuppetDistroFact
    family: str
    release: PuppetOSReleaseFact
    architecture: str


class PuppetHostFacts(typing.TypedDict):
    os: PuppetOSFact
    uptime: str


class PuppetTrustedFacts(typing.TypedDict):
    domain: str
    certname: str
    hostname: str


class PuppetInventoryHost(typing.TypedDict):
    certname: str
    timestamp: str
    environment: str
    facts: PuppetHostFacts
    trusted: PuppetTrustedFacts

    @property
    def last_contact(self) -> str:
        return self["timestamp"]


class EMFPuppetInfo(typing.TypedDict):
    location: str
    description: str


class PuppetNode(typing.TypedDict):
    certname: str
    catalog_environment: str
    facts_environment: str
    report_environment: str
    catalog_timestamp: str  # ISO-8601
    facts_timestamp: str  # ISO-8601
    report_timestamp: str  # ISO-8601
    latest_report_status: str  # changed/unchanged/failed
    latest_report_noop: bool
    latest_report_noop_pending: bool
    latest_report_corrective_change: str | None
    latest_report_hash: str
    latest_report_job_id: str | None


class BasePuppetDBClient(abc.ABC):
    @abc.abstractmethod
    async def query_inventory(self) -> list[PuppetInventoryHost]:
        pass

    @abc.abstractmethod
    async def query_resources(self, query: PQL) -> list[dict[str, typing.Any]]:
        pass

    @abc.abstractmethod
    async def query_emf_info(self) -> dict[str, EMFPuppetInfo]:
        pass

    @abc.abstractmethod
    async def query_nodes(self) -> list[PuppetNode]:
        pass


class PuppetDBClientException(Exception):
    pass


type PQL = list[str | PQL]


class PuppetDBClient(BasePuppetDBClient):
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def query_inventory(self) -> list[PuppetInventoryHost]:
        try:
            async with self.session.get("/pdb/query/v4/inventory") as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise PuppetDBClientException(f"Failed to fetch inventory from PuppetDB: {e}") from e

    async def query_resources(self, query: PQL) -> list[dict[str, typing.Any]]:
        try:
            async with self.session.get("/pdb/query/v4/resources", params={"query": json.dumps(query)}) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise PuppetDBClientException(f"Failed to fetch resources from PuppetDB: {e}") from e

    async def query_emf_info(self) -> dict[str, EMFPuppetInfo]:
        data = await self.query_resources(["=", "type", "Emf_facts::Emf_host_info"])
        return {resource["certname"]: resource["parameters"] for resource in data}

    async def query_nodes(self) -> list[PuppetNode]:
        try:
            async with self.session.get("/pdb/query/v4/nodes") as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            raise PuppetDBClientException(f"Failed to fetch nodes from PuppetDB: {e}") from e
        pass


class DummyPuppetDBClient(BasePuppetDBClient):
    async def query_inventory(self) -> list[PuppetInventoryHost]:
        logger.error("PuppetDB querying is disabled (DummyPuppetDBClient in use)")
        return []

    async def query_resources(self, query: PQL) -> list[dict[str, typing.Any]]:
        logger.error("PuppetDB querying is disabled (DummyPuppetDBClient in use)")
        return []

    async def query_emf_info(self) -> dict[str, EMFPuppetInfo]:
        logger.error("PuppetDB querying is disabled (DummyPuppetDBClient in use)")
        return {}

    async def query_nodes(self) -> list[PuppetNode]:
        logger.error("PuppetDB querying is disabled (DummyPuppetDBClient in use)")
        return []


@asynccontextmanager
async def make_puppetdb_client(
    api_url: str | None,
    cacert_path: str | None,
    cert_path: str | None,
    privkey_path: str | None,
    ssl_verify_hostname: bool = True,
):
    if not (api_url and cacert_path and cert_path and privkey_path):
        logger.warning("PuppetDB querying is disabled (api_url/cacert_path/cert_path/privkey_path missing)")
        yield DummyPuppetDBClient()
        return

    context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=cacert_path)
    context.check_hostname = ssl_verify_hostname
    context.load_cert_chain(certfile=cert_path, keyfile=privkey_path)
    async with aiohttp.ClientSession(
        base_url=api_url,
        connector=aiohttp.TCPConnector(ssl=context),
    ) as session:
        assert session
        yield PuppetDBClient(session)

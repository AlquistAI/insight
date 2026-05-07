# -*- coding: utf-8 -*-
"""
    scripts.find_orphaned_resources
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Find resources that do not belong to any project and/or knowledge base.

    ToDo: Kronos resources in Azure Storage that do not belong to any KB.
    ToDo: Kronos KB that is not present in Ragnarok.
    ToDo: Option to automatically delete orphaned resources.
"""

from collections import defaultdict
from time import sleep

import requests
from tqdm import tqdm

from common.config import CONFIG
from common.models.enums import Coll

KRONOS_URL = str(CONFIG.KRONOS_URL).rstrip("/")
RAGNAROK_URL = str(CONFIG.RAGNAROK_URL).rstrip("/")

HEADERS_KRONOS = {"accept": "application/json", "X-Api-Key": CONFIG.KRONOS_API_KEY.get_secret_value()}
HEADERS_RAGNAROK = {"accept": "application/json", "Authorization": CONFIG.RAGNAROK_API_KEY.get_secret_value()}


def get_kronos_project_ids() -> set[str]:
    """Get project IDs present in Kronos."""

    print("Loading Kronos project IDs...", end=" ")

    res = requests.get(
        url=f"{KRONOS_URL}/projects/",
        params={"per_page": 0, "fields": "_id"},
        headers=HEADERS_KRONOS,
    )

    res.raise_for_status()
    res = res.json()["data"]

    print(f"{len(res)} loaded")
    return {x["_id"] for x in res}


def get_kronos_db_ids_per_project(coll_name: Coll) -> dict[str, set[str]]:
    """
    Get MongoDB document IDs per project present in Kronos.

    :param coll_name: DB collection name
    :return: set of document IDs
    """

    print(f"Loading Kronos document IDs from collection '{coll_name.value}'...", end=" ")

    res = requests.get(
        url=f"{KRONOS_URL}/{coll_name.value}/",
        params={"per_page": 0, "fields": "project_id"},
        headers=HEADERS_KRONOS,
    )

    res.raise_for_status()
    res = res.json()["data"]

    out = defaultdict(list)
    for x in res:
        out[x["project_id"]].append(x["_id"])

    print(f"{len(res)} loaded")
    return {k: set(v) for k, v in out.items()}


def get_kronos_resources_per_project() -> dict[str, set[str]]:
    """Get resources per project present in Kronos."""

    print("Loading Kronos resources...", end=" ")

    res = requests.get(
        url=f"{KRONOS_URL}/resources/",
        headers=HEADERS_KRONOS,
    )

    res.raise_for_status()
    res = res.json()

    out = defaultdict(list)
    for x in res:
        xs = x.split("/")
        if xs[1] == "projects":
            out[xs[2]].append(x)

    print(f"{len(res)} loaded")
    return {k: set(v) for k, v in out.items()}


def get_ragnarok_project_ids() -> set[str]:
    """Get project IDs present in Ragnarok."""

    print("Loading Ragnarok project IDs...", end=" ")

    res = requests.get(
        url=f"{RAGNAROK_URL}/projects/",
        headers=HEADERS_RAGNAROK,
    )

    res.raise_for_status()
    res = res.json()

    print(f"{len(res)} loaded")
    return set(res)


def get_ragnarok_kb_ids_per_project(project_ids: set[str]) -> dict[str, set[str]]:
    """Get knowledge base IDs per project present in Ragnarok."""

    out = {}
    sleep(0.5)

    for pid in tqdm(project_ids, desc="Loading Ragnarok KB"):
        res = requests.get(
            url=f"{RAGNAROK_URL}/knowledge_base/",
            params={"project_id": pid},
            headers=HEADERS_RAGNAROK,
        )

        res.raise_for_status()
        out[pid] = set(res.json())

    sleep(0.5)
    return out


if __name__ == "__main__":
    # Load Kronos data
    kronos_project_ids = get_kronos_project_ids()
    kronos_kb_ids = get_kronos_db_ids_per_project(Coll.KB)
    kronos_session_ids = get_kronos_db_ids_per_project(Coll.SESSIONS)
    kronos_turn_ids = get_kronos_db_ids_per_project(Coll.TURNS)
    kronos_resources = get_kronos_resources_per_project()
    print("-----")

    # Load Ragnarok data
    ragnarok_project_ids = get_ragnarok_project_ids()
    ragnarok_kb_ids = get_ragnarok_kb_ids_per_project(ragnarok_project_ids)
    print("-----")

    # Check empty projects in Kronos
    for k_pid in kronos_project_ids:
        if k_pid not in kronos_kb_ids:
            print(f"Kronos project '{k_pid}' is empty")
            kronos_kb_ids[k_pid] = set()

    # Check orphaned documents in DB
    for res_name, res_ids in (
            ("KB", kronos_kb_ids),
            ("Session", kronos_session_ids),
            ("Turn", kronos_turn_ids),
    ):
        for k_pid in res_ids:
            if k_pid not in kronos_project_ids:
                print(f"{res_name} for non-existing project '{k_pid}' present in Kronos")

    # Check orphaned resources in Kronos
    for k_pid in kronos_resources:
        if k_pid not in kronos_project_ids:
            print(f"Resource for non-existing project '{k_pid}' present in Kronos")

    # Check orphaned resources in Ragnarok
    for r_pid in ragnarok_project_ids:
        if r_pid not in kronos_project_ids:
            print(f"Ragnarok project '{r_pid}' not present in Kronos")
            continue

        k_kb_ids = kronos_kb_ids[r_pid]
        for r_kid in ragnarok_kb_ids[r_pid]:
            if r_kid not in k_kb_ids:
                print(f"Ragnarok KB '{r_kid}' (project '{r_pid}') not present in Kronos")

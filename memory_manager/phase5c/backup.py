"""Offline capacity/integrity plan only. No copy, SSH, deletion or restore execution."""
from pathlib import PurePosixPath

SIZE = 168229376
SHA256 = '92f138189be20e3256d150b744f15cb12ee46240aae4b29e1f3935c09b1d0a9f'
RESTORED_ESTIMATE = 307330079


def plan(destination, available_bytes):
    if not isinstance(destination,str) or not PurePosixPath(destination).is_absolute() or '..' in PurePosixPath(destination).parts:
        raise ValueError('Explicit private destination on a separately approved host required')
    required=SIZE+2*RESTORED_ESTIMATE+1024**3
    if type(available_bytes) is not int or available_bytes < required:
        raise ValueError('Capacity below archive + two restore copies + 1 GiB reserve')
    return {'mode':'plan-only','transfer_authorized':False,'restore_authorized':False,
            'source_manifest':'/var/lib/jarvis-memory/phase5-backup/20261114T181811Z-3eb75693/manifest.json',
            'destination':destination,'archive_bytes':SIZE,'archive_sha256':SHA256,
            'required_available_bytes':required,'restored_bytes_estimate':RESTORED_ESTIMATE,
            'qdrant_version':'1.20.0','expected_snapshot_point_count':41428,
            'requires_independent_storage_attestation':True,
            'steps':['fresh source SHA256/size check without payload export',
                     'exclusive partial file under 0700 destination; encrypted transport after approval',
                     'fsync; verify destination size/SHA256; atomic rename only to new path',
                     'isolated pinned Qdrant restore into new directory with private network and dedicated key',
                     'compare count/schema/indexes; authenticated probe without payload; stop owned verifier',
                     'private receipt plus nonsensitive public summary; keep source and failed copies']}

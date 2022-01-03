from pathlib import Path
import sys
import requests
from opendrift.models.openoil.adios.oil import OpendriftOil

import coloredlogs
import logging
logger = logging.getLogger('harvest_oils')

ADIOS = "https://adios.orr.noaa.gov/api/oils/"

def get_full_oil_from_id(_id):
    logger.debug(f"Fetching full oil: {_id}")
    o = requests.get(f"{ADIOS}/{_id}")
    o.raise_for_status()
    return OpendriftOil(o.json())

def oils(limit=50, query=''):
    """
    Get all oils.

    Args:

        limit: number of oils to retrieve, None means all available.
        query: search string (name, id, location).


    Returns:

        List of `class:ThinOil`s.
    """
    # The batch size seems to be maximum 205 at the moment.
    MAX_BATCH_SZ = 205

    batch = min(MAX_BATCH_SZ, limit if limit is not None else MAX_BATCH_SZ)

    oils = []

    # XXX: This may fail when batch size is less or unequal to `batch`.
    while limit is None or len(oils) < limit:
        p = int(len(oils) / batch)  # next page, XXX: check for off-by-one?
        logging.debug(
            f"Requesting list of oils from ADIOS, oils: {len(oils)}, page: {p}"
        )

        o = requests.get(ADIOS, {
            'dir': 'asc',
            'limit': batch,
            'page': p,
            'sort': 'metadata.name',
            'q': query
        })
        o.raise_for_status()
        o = o.json()

        oils.extend(o['data'])

        if len(oils) >= int(o['meta']['total']) or (limit is not None and len(oils) >= limit):
            break

    logger.info(f"Fetched {len(oils)} oils from ADIOS")

    limit = len(oils) if limit is None else limit
    oils = oils[:min(limit, len(oils))]
    oils = [o['_id'] for o in oils]

    return oils

def download(dst):
    logger.info('downloading all oils..')

    for o in oils(None):
        logger.info(f"fetching oil: {o}..")
        o = get_full_oil_from_id(o)
        if o.valid():
            f = dst / Path(o.id).with_suffix('.json')
            with open(f, 'w') as fd:
                fd.write(o.json())
        else:
            logger.warning(f'skipping invalid oil: {o.id}')

def make_archive(oildir, file):
    logger.info(f'making archive: {oildir / "*.json"}')

    # Making a big JSON array with oils as a dictionary each.
    oils = []

    import glob
    import json
    import lzma
    for f in glob.glob(str(oildir / '*.json')):
        with open(f, 'r') as fd:
            oils.append(json.load(fd))

    logger.info(f'added {len(oils)} oils..')
    logger.info(f'compressing to {file}..')
    with lzma.open(file, 'wt') as c:
        json.dump(oils, c)


if __name__ == '__main__':
    coloredlogs.install('debug')

    dst = Path('oils')

    if not dst.exists():
        raise Exception(f"destination path does not exist: {dst}")

    if not '--skip-download' in sys.argv:
        download(dst)

    make_archive(dst, 'oils.xz')

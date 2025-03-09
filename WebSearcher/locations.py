import os
import io
import csv
import base64
import zipfile
import requests
from google.protobuf.internal import decoder, encoder  # poetry add protobuf
from typing import Dict, Union, Any

from . import logger
from . import webutils as wu
log = logger.Logger().start(__name__)


def convert_canonical_name_to_uule(canon_name: str) -> str:
    """
    Get UULE parameter based on a location's canonical name.
    Args: canon_name: Canonical name of the location
    Returns: UULE parameter for Google search
    """
    fields = {1: 2, 2: 32, 4: canon_name}
    encoded_string = encode_protobuf_string(fields)
    return f'w+{encoded_string}'


def encode_protobuf_string(fields: Dict[int, Union[str, int]]) -> str:
    """
    Encode a dictionary of field numbers and values into a base64-encoded protobuf string.
    Args: fields: A dictionary where keys are protobuf field numbers and values are the data to encode
    Returns: A base64-encoded protobuf message string
    """
    encoded = bytearray()  # Buffer to store encoded bytes

    for field_number, value in fields.items():
        wire_type = 2 if isinstance(value, str) else 0  # Determine wire type based on value type
        tag = field_number << 3 | wire_type             # Combine field number and wire type into tag
        encoded.extend(encoder._VarintBytes(tag))       # Encode the tag into bytes
        
        # Encode the value based on wire type
        if wire_type == 0:
            encoded.extend(encoder._VarintBytes(value))       # Encode the integer as varint
        if wire_type == 2:
            value = value.encode('utf-8')                     # Convert string to bytes
            encoded.extend(encoder._VarintBytes(len(value)))  # Add length prefix
            encoded.extend(value)                             # Add the actual bytes
    
    return base64.b64encode(bytes(encoded)).decode('utf-8')   # Convert to base64 and decode to string


def decode_protobuf_string(encoded_string: str) -> Dict[int, Any]:
    """
    Decode a base64-encoded protobuf string into a dictionary of field numbers and values.
    Args: encoded_string: A base64-encoded protobuf message
    Returns: dictionary where keys are protobuf field numbers and values are the decoded values
    """

    pos = 0       # Position tracker for decoding
    fields = {}   # Dictionary to store decoded field numbers and values

    protobuf_bytes = base64.b64decode(encoded_string) # Convert to protobuf bytes
    while pos < len(protobuf_bytes):

        # Get field number and wire type
        tag, pos_new = decoder._DecodeVarint(protobuf_bytes, pos) # Each protobuf field starts with a varint tag
        field_number, wire_type = tag >> 3, tag & 7               # Extract field number and wire type from tag
        
        # Decode value based on wire type (0: varint, 2: length-delimited; others not supported)
        if wire_type == 0:
            value, pos_new = decoder._DecodeVarint(protobuf_bytes, pos_new)    # Get the varint value and new position
        elif wire_type == 2:
            length, pos_start = decoder._DecodeVarint(protobuf_bytes, pos_new) # Get length and starting position
            value = protobuf_bytes[pos_start:pos_start + length]               # Extract data based on the length
            pos_new = pos_start + length                                       # Update the new position
            value = value.decode('utf-8')                                      # Assume UTF-8 encoding for strings
        
        fields[field_number] = value    # Store the field number and value in the dictionary
        pos = pos_new                   # Move to the next field using the updated position
    return fields


def download_locations(
        data_dir: str = "data/locations", 
        url: str = "https://developers.google.com/adwords/api/docs/appendix/geotargeting"
    ) -> None:
    """Download the latest geolocations, check if already exists locally first.

    Args:
        data_dir (str): Where to save the data as a csv
        url (str, optional): Defaults to the current URL

    Returns:
        None: Saves to file in the default or selected data_dir

    """
    os.makedirs(data_dir, exist_ok=True)

    url_latest = get_latest_url(url)
    fp = os.path.join(data_dir, url_latest.split('/')[-1])
    fp_unzip = fp.replace('.zip', '')

    # Check if the current version already exists
    if os.path.exists(fp):
        print(f"Version up to date: {fp}")
    elif os.path.exists(fp_unzip):
        print(f"Version up to date: {fp_unzip}")
    else:
        print(f"Version out of date")
        # Download and save
        try:
            print(f'getting: {url_latest}')
            response = requests.get(url_latest)
        except Exception:
            log.exception('Failed to retrieve location data')

        if fp.endswith('.zip'):
            save_zip_response(response, fp_unzip)
        else:
            lines = response.content.decode('utf-8').split('\n')
            locations = [l for l in csv.reader(lines, delimiter=',')]
            write_csv(fp_unzip, locations)


def get_latest_url(url:str):
    try:
        html = requests.get(url).content
        soup = wu.make_soup(html)
        url_list = [url for url in wu.get_link_list(soup) if url and url != '']
        geo_urls = [url for url in url_list if 'geotargets' in url]

        # Get current CSV url and use as filename
        geo_url = sorted(geo_urls)[-1]
        url_latest = 'https://developers.google.com' + geo_url
        return url_latest

    except Exception:
        log.exception("Failed to retrieve location data url")


def save_zip_response(response: requests.Response, fp: str) -> None:
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
        for member in zip_ref.namelist():
            if member.endswith('.csv'):
                with zip_ref.open(member) as csv_file:
                    reader = csv.reader(io.TextIOWrapper(csv_file, 'utf-8'))
                    write_csv(fp, reader=reader)


def write_csv(fp: str, lines: list = None, reader: csv.reader = None) -> None:
    with open(fp, 'w', encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        if reader:
            writer.writerows(reader)
        elif lines:
            writer.writerows(lines)
    print(f"saved: {fp}")

